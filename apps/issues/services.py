from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.campaigns.models import Campaign


PRIORITY_ORDER = ["low", "medium", "high", "critical"]
SLA_RULES = {
    "critical": (timedelta(hours=1), timedelta(hours=12)),
    "high": (timedelta(hours=4), timedelta(hours=24)),
    "medium": (timedelta(hours=8), timedelta(hours=48)),
    "low": (timedelta(hours=24), timedelta(hours=72)),
}
CRITICAL_KEYWORDS = ("storm", "collapsed", "torn", "danger")


def _bump(priority: str) -> str:
    index = min(PRIORITY_ORDER.index(priority) + 1, len(PRIORITY_ORDER) - 1)
    return PRIORITY_ORDER[index]


def _campaign_is_active(booking) -> bool:
    today = timezone.localdate()
    campaign = booking.campaign
    return campaign.status == Campaign.Status.ACTIVE or (campaign.start_date <= today <= campaign.end_date)


def calculate_auto_priority(issue):
    from .models import Issue

    priority = Issue.Priority.MEDIUM
    reasons = ["Base priority set to medium."]
    description = (issue.description or "").lower()

    if issue.issue_type == Issue.IssueType.MISSING:
        priority = Issue.Priority.HIGH
        reasons.append("Missing inventory or creative issue raised priority to high.")

    if any(keyword in description for keyword in CRITICAL_KEYWORDS):
        priority = Issue.Priority.CRITICAL
        reasons.append("Critical safety/weather keyword detected.")

    if issue.reporter_type == Issue.ReporterType.CLIENT and priority != Issue.Priority.CRITICAL:
        priority = _bump(priority)
        reasons.append("Client-reported issue raised priority by one level.")

    if issue.booking_id and _campaign_is_active(issue.booking) and priority != Issue.Priority.CRITICAL:
        priority = _bump(priority)
        reasons.append("Active campaign raised priority by one level.")

    return priority, " ".join(reasons)


def calculate_sla_status(issue, now=None):
    from .models import Issue

    now = now or timezone.now()
    if issue.resolved_at and issue.resolution_due_at and issue.resolved_at > issue.resolution_due_at:
        return Issue.SlaStatus.BREACHED
    if issue.status == Issue.Status.RESOLVED:
        return Issue.SlaStatus.ON_TRACK
    if issue.resolution_due_at and now > issue.resolution_due_at:
        return Issue.SlaStatus.BREACHED
    if issue.first_response_due_at and not issue.acknowledged_at and now > issue.first_response_due_at:
        return Issue.SlaStatus.AT_RISK
    return Issue.SlaStatus.ON_TRACK


def prepare_issue_for_save(issue, *, is_create: bool):
    from .models import Issue

    now = timezone.now()
    if is_create:
        priority, reason = calculate_auto_priority(issue)
        issue.priority = priority
        issue.priority_reason = reason
        first_response_delta, resolution_delta = SLA_RULES[priority]
        issue.first_response_due_at = now + first_response_delta
        issue.resolution_due_at = now + resolution_delta

    if issue.status in {Issue.Status.ACKNOWLEDGED, Issue.Status.IN_PROGRESS, Issue.Status.RESOLVED}:
        issue.acknowledged_at = issue.acknowledged_at or now

    issue.sla_status = calculate_sla_status(issue, now=now)


def sync_issue_sla_status(issue):
    next_status = calculate_sla_status(issue)
    if issue.pk and next_status != issue.sla_status:
        issue.sla_status = next_status
        issue.__class__.objects.filter(pk=issue.pk).update(sla_status=next_status, updated_at=timezone.now())
    return issue.sla_status


def should_auto_escalate_issue(issue) -> bool:
    from .models import Issue

    return issue.priority in {Issue.Priority.HIGH, Issue.Priority.CRITICAL} or issue.sla_status == Issue.SlaStatus.BREACHED


def escalate_issue(issue, *, actor=None, reason: str = "", auto: bool = False):
    from .models import IssueEvent

    if issue.escalated_at:
        return issue

    issue.escalated_at = timezone.now()
    issue.escalated_by = actor if getattr(actor, "is_authenticated", False) else None
    issue.escalation_reason = (reason or "").strip() or ("Auto-escalated by SLA/priority rules." if auto else "Issue escalated.")
    issue.save(update_fields=["escalated_at", "escalated_by", "escalation_reason", "updated_at"])
    IssueEvent.objects.create(
        issue=issue,
        actor=issue.escalated_by,
        event_type=IssueEvent.EventType.ESCALATED,
        message=issue.escalation_reason,
        metadata={"auto": auto, "priority": issue.priority, "sla_status": issue.sla_status},
    )
    try:
        from apps.notifications.services import trigger_issue_escalated_notification

        trigger_issue_escalated_notification(issue, actor=issue.escalated_by)
    except Exception:
        pass
    return issue


def build_public_issue_report_url(token: str) -> str:
    base_url = settings.FRONTEND_PUBLIC_BASE_URL.rstrip("/")
    return f"{base_url}/report-issue/{token}"


def resolve_open_issues_after_poe(booking, poe_created_at=None):
    from .models import Issue, IssueEvent

    poe_created_at = poe_created_at or timezone.now()
    queryset = Issue.objects.filter(booking=booking).exclude(status=Issue.Status.RESOLVED)
    for issue in queryset:
        if issue.created_at and poe_created_at <= issue.created_at:
            continue
        issue.status = Issue.Status.RESOLVED
        issue.save(update_fields=["status", "resolved_at", "sla_status", "updated_at"])
        IssueEvent.objects.create(
            issue=issue,
            event_type=IssueEvent.EventType.AUTO_RESOLVED,
            message="Issue auto-resolved after replacement POE upload.",
            metadata={"poe_created_at": poe_created_at.isoformat()},
        )
