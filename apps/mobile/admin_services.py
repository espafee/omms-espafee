from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import Assignment, Booking
from apps.billing.models import Invoice
from apps.billing.services import build_collection_efficiency_analytics
from apps.campaigns.models import Campaign
from apps.campaigns.services import build_campaign_performance_analytics
from apps.issues.models import Issue
from apps.issues.services import sync_issue_sla_status
from apps.observability.services import (
    build_operational_heatmap_intelligence,
    build_poe_sla_intelligence,
    build_predictive_operations_intelligence,
    build_system_health_diagnostics,
)
from apps.poe.models import ProofOfExecution
from apps.tenants.services import scope_queryset_to_tenant_path
from core.images import build_public_media_url


FAILED_STATUS = "failed"
STATUS_FILTER_MAP = {
    "pending": ProofOfExecution.VerificationStatus.PENDING,
    "verified": ProofOfExecution.VerificationStatus.VERIFIED,
    "suspicious": ProofOfExecution.VerificationStatus.SUSPICIOUS,
    FAILED_STATUS: ProofOfExecution.VerificationStatus.REJECTED,
}


def _base_booking_queryset(user=None):
    queryset = (
        Booking.objects.select_related("campaign", "campaign__client", "media_unit", "media_unit__site")
        .prefetch_related("assignments__user", "poe_records__media_items", "poe_records__verification_logs")
        .exclude(status=Booking.Status.CANCELLED)
    )
    return scope_queryset_to_tenant_path(queryset, user, "campaign__tenant")


def _active_campaign_queryset(today, user=None):
    queryset = (
        Campaign.objects.select_related("client")
        .filter(Q(status=Campaign.Status.ACTIVE) | Q(start_date__lte=today, end_date__gte=today))
        .distinct()
        .order_by("end_date", "id")
    )
    return scope_queryset_to_tenant_path(queryset, user)


def _poe_queryset(user=None):
    queryset = ProofOfExecution.objects.select_related(
        "checked_by",
        "booking",
        "booking__campaign",
        "booking__media_unit",
        "booking__media_unit__site",
    ).prefetch_related("booking__assignments__user", "media_items", "verification_logs")
    return scope_queryset_to_tenant_path(queryset, user, "booking__campaign__tenant")


def _issue_queryset(user=None):
    queryset = Issue.objects.select_related(
        "booking__campaign",
        "booking__media_unit__site",
        "reported_by",
    )
    return scope_queryset_to_tenant_path(queryset, user, "booking__campaign__tenant")


def _latest_poe(booking):
    return booking.poe_records.order_by("-captured_at", "-created_at", "-id").first()


def _has_verified_poe(booking) -> bool:
    return booking.poe_records.filter(verification_status=ProofOfExecution.VerificationStatus.VERIFIED).exists()


def _is_poe_pending(booking) -> bool:
    latest = _latest_poe(booking)
    return latest is None or latest.verification_status == ProofOfExecution.VerificationStatus.PENDING


def _has_any_poe(booking) -> bool:
    return booking.poe_records.exists()


def _active_assignment(booking):
    return booking.assignments.select_related("user").filter(status=Assignment.Status.PENDING).first()


def _overdue_assignment_bookings(today, user=None):
    return [
        booking
        for booking in _base_booking_queryset(user).filter(
            assignments__status=Assignment.Status.PENDING,
            start_date__lte=today,
        ).distinct()
        if not _has_any_poe(booking)
    ]


def _assignee_label(booking) -> str:
    assignment = booking.assignments.select_related("user").exclude(status=Assignment.Status.CANCELLED).first()
    if not assignment:
        return ""
    return assignment.user.get_full_name() or assignment.user.email


def _client_label(campaign) -> str:
    return campaign.client.organization_name or campaign.client.get_full_name() or campaign.client.email


def _activity_item(booking, *, due_date, status):
    site = booking.media_unit.site
    return {
        "booking_id": booking.id,
        "campaign_name": booking.campaign.name,
        "site_name": site.name,
        "unit_name": booking.media_unit.unit_code,
        "assigned_to": _assignee_label(booking),
        "due_date": due_date,
        "status": status,
    }


def _latest_distance(poe_record):
    latest_log = poe_record.verification_logs.order_by("-created_at", "-id").first()
    return latest_log.distance_meters if latest_log else None


def _latest_image_url(poe_record, request=None):
    media = poe_record.media_items.order_by("-captured_at", "-created_at", "-id").first()
    if not media:
        return None
    if media.media_url:
        return media.media_url
    return build_public_media_url(media.image, request=request)


class MobileAdminOperationsService:
    @staticmethod
    def get_overview(user=None):
        today = timezone.localdate()
        tenant_filters = {"_user": user}
        bookings = _base_booking_queryset(user)
        poe_sla = build_poe_sla_intelligence(tenant_filters)
        billing_queryset = scope_queryset_to_tenant_path(Invoice.objects.all(), user, "campaign__tenant")
        billing = build_collection_efficiency_analytics(billing_queryset)
        campaigns = build_campaign_performance_analytics(user=user)
        system_health = build_system_health_diagnostics()
        heatmap = build_operational_heatmap_intelligence(tenant_filters)
        predictive = build_predictive_operations_intelligence(
            poe_sla=poe_sla,
            campaign_performance=campaigns,
            billing_intelligence=billing,
            operational_heatmap=heatmap,
            kpis={},
            can_view_finance=True,
        )
        environment_mode = system_health.get("environment_mode", {})
        top_busy_region = heatmap.get("top_busy_region") or {}
        top_suspicious_region = heatmap.get("top_suspicious_region") or {}
        active_alerts = len([alert for alert in MobileAdminOperationsService.get_alerts(user=user) if alert["severity"] in {"warning", "danger"}])
        poe_queryset = _poe_queryset(user)
        return {
            "active_campaigns": _active_campaign_queryset(today, user).count(),
            "campaigns_at_risk": campaigns["at_risk_count"],
            "campaigns_ending_soon": campaigns["ending_soon_count"],
            "critical_campaigns": campaigns["critical_count"],
            "poe_pending": sum(1 for booking in bookings if _is_poe_pending(booking)),
            "poe_completed_today": poe_queryset.filter(
                captured_at__date=today,
                verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
            ).count(),
            "suspicious_poe": poe_queryset.filter(
                verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS
            ).count(),
            "poe_sla_warnings": poe_sla["warning_count"],
            "poe_sla_breaches": poe_sla["breach_count"],
            "overdue_invoices": billing["overdue_invoice_count"],
            "overdue_invoice_value": billing["overdue_amount"],
            "collection_efficiency": billing["collection_efficiency_percentage"],
            "bookings_starting_today": _base_booking_queryset(user).filter(start_date=today).count(),
            "bookings_ending_today": _base_booking_queryset(user).filter(end_date=today).count(),
            "system_status": system_health["status"],
            "api_status": system_health["api_status"],
            "environment_mode": environment_mode.get("mode", "normal"),
            "environment_mode_label": environment_mode.get("label", "Normal"),
            "environment_mode_message": environment_mode.get("message", ""),
            "environment_write_blocking": bool(environment_mode.get("is_write_blocking", False)),
            "failed_jobs": system_health["recent_failed_background_jobs"],
            "active_alerts": active_alerts,
            "operational_hotspot_label": top_busy_region.get("region") or "No busy area",
            "operational_hotspot_activity": top_busy_region.get("total_uploads", 0),
            "suspicious_hotspot_label": top_suspicious_region.get("region") or "No suspicious area",
            "suspicious_hotspot_count": top_suspicious_region.get("suspicious_count", 0),
            "predictive_priority_label": predictive["summary"]["plain_language"],
            "predictive_risk_level": predictive["summary"]["highest_risk_level"],
            "predictive_confidence": predictive["summary"]["confidence"],
        }

    @staticmethod
    def get_running_campaigns(user=None):
        today = timezone.localdate()
        items = []
        for campaign in _active_campaign_queryset(today, user).prefetch_related("bookings__poe_records"):
            campaign_bookings = [booking for booking in campaign.bookings.all() if booking.status != Booking.Status.CANCELLED]
            total_units = len({booking.media_unit_id for booking in campaign_bookings})
            poe_completed = sum(1 for booking in campaign_bookings if _has_verified_poe(booking))
            poe_pending = max(total_units - poe_completed, 0)
            progress = round((poe_completed / total_units) * 100) if total_units else 0
            items.append(
                {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "client_name": _client_label(campaign),
                    "start_date": campaign.start_date,
                    "end_date": campaign.end_date,
                    "total_units": total_units,
                    "poe_completed": poe_completed,
                    "poe_pending": poe_pending,
                    "poe_progress_percent": progress,
                    "status": campaign.status,
                }
            )
        return items

    @staticmethod
    def get_poe_tracker(*, status_filter=None, request=None, user=None):
        queryset = _poe_queryset(user)
        mapped_status = STATUS_FILTER_MAP.get(status_filter or "")
        if mapped_status:
            queryset = queryset.filter(verification_status=mapped_status)

        items = []
        for poe_record in queryset.order_by("-captured_at", "-created_at", "-id"):
            booking = poe_record.booking
            site = booking.media_unit.site
            status_value = FAILED_STATUS if poe_record.verification_status == ProofOfExecution.VerificationStatus.REJECTED else poe_record.verification_status
            items.append(
                {
                    "poe_id": poe_record.id,
                    "booking_id": booking.id,
                    "campaign_name": booking.campaign.name,
                    "site_name": site.name,
                    "unit_name": booking.media_unit.unit_code,
                    "field_staff": _assignee_label(booking),
                    "submitted_at": poe_record.captured_at,
                    "status": status_value,
                    "distance_meters": _latest_distance(poe_record),
                    "image_url": _latest_image_url(poe_record, request=request),
                }
            )
        return items

    @staticmethod
    def get_daily_activity(user=None):
        today = timezone.localdate()
        active_bookings = _base_booking_queryset(user).filter(start_date__lte=today, end_date__gte=today)
        overdue_assignment_ids = {booking.id for booking in _overdue_assignment_bookings(today, user)}
        return {
            "date": today,
            "installations_due_today": [
                _activity_item(booking, due_date=booking.start_date, status="installation_due")
                for booking in _base_booking_queryset(user).filter(start_date=today)
            ],
            "poe_pending_today": [
                _activity_item(booking, due_date=today, status="poe_pending")
                for booking in active_bookings
                if _is_poe_pending(booking)
            ],
            "overdue_items": [
                _activity_item(booking, due_date=booking.end_date, status="overdue")
                for booking in _base_booking_queryset(user).filter(end_date__lt=today)
                if not _has_verified_poe(booking) and booking.id not in overdue_assignment_ids
            ]
            + [
                _activity_item(booking, due_date=booking.start_date, status="overdue")
                for booking in _overdue_assignment_bookings(today, user)
            ],
        }

    @staticmethod
    def get_alerts(user=None):
        today = timezone.localdate()
        now = timezone.now()
        alerts = []

        for booking in _base_booking_queryset(user).filter(end_date__lt=today):
            if not _has_verified_poe(booking):
                alerts.append(
                    {
                        "type": "overdue_poe",
                        "severity": "warning",
                        "title": "POE overdue",
                        "message": f"{booking.campaign.name} at {booking.media_unit.site.name} is overdue.",
                        "related_id": booking.id,
                        "created_at": now,
                    }
                )

        for booking in _overdue_assignment_bookings(today, user):
            assignment = _active_assignment(booking)
            assigned_to = assignment.user.get_full_name() or assignment.user.email if assignment else "field staff"
            alerts.append(
                {
                    "type": "overdue_assignment",
                    "severity": "warning",
                    "title": "Assignment overdue",
                    "message": f"POE pending for {booking.campaign.name} at {booking.media_unit.site.name} assigned to {assigned_to}.",
                    "related_id": booking.id,
                    "created_at": now,
                }
            )

        for poe_record in _poe_queryset(user).filter(
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS
        ):
            alerts.append(
                {
                    "type": "suspicious_poe",
                    "severity": "danger",
                    "title": "Suspicious POE",
                    "message": f"{poe_record.booking.campaign.name} at {poe_record.booking.media_unit.site.name} needs review.",
                    "related_id": poe_record.id,
                    "created_at": poe_record.updated_at,
                }
            )

        for poe_record in _poe_queryset(user).filter(
            verification_status=ProofOfExecution.VerificationStatus.REJECTED
        ):
            alerts.append(
                {
                    "type": "failed_verification",
                    "severity": "danger",
                    "title": "POE verification failed",
                    "message": f"{poe_record.booking.campaign.name} at {poe_record.booking.media_unit.site.name} failed verification.",
                    "related_id": poe_record.id,
                    "created_at": poe_record.updated_at,
                }
            )

        ending_cutoff = today + timedelta(days=3)
        for campaign in _active_campaign_queryset(today, user).filter(end_date__gte=today, end_date__lte=ending_cutoff).exclude(
            status__in=[Campaign.Status.COMPLETED, Campaign.Status.CANCELLED]
        ):
            alerts.append(
                {
                    "type": "campaign_ending_soon",
                    "severity": "info",
                    "title": "Campaign ending soon",
                    "message": f"{campaign.name} ends on {campaign.end_date}.",
                    "related_id": campaign.id,
                    "created_at": now,
                }
            )

        for issue in _issue_queryset(user).exclude(status=Issue.Status.RESOLVED):
            sync_issue_sla_status(issue)
            if issue.sla_status == Issue.SlaStatus.BREACHED:
                alert_type = "issue_sla_breached"
                severity = "danger"
                title = "Issue SLA breached"
            elif issue.sla_status == Issue.SlaStatus.AT_RISK:
                alert_type = "issue_sla_at_risk"
                severity = "warning"
                title = "Issue SLA at risk"
            else:
                alert_type = "reported_issue"
                severity = "danger" if issue.priority in [Issue.Priority.HIGH, Issue.Priority.CRITICAL] else "warning"
                title = "Issue reported"
            alerts.append(
                {
                    "type": alert_type,
                    "severity": severity,
                    "title": title,
                    "message": f"{issue.get_issue_type_display()} issue for {issue.booking.campaign.name} at {issue.booking.media_unit.site.name}.",
                    "related_id": issue.id,
                    "created_at": issue.created_at,
                }
            )

        return sorted(alerts, key=lambda item: item["created_at"], reverse=True)

    @staticmethod
    def get_issues(request=None, user=None):
        items = []
        queryset = _issue_queryset(user).order_by("-created_at")
        for issue in queryset:
            sync_issue_sla_status(issue)
            booking = issue.booking
            site = booking.media_unit.site
            reporter = issue.reported_by.get_full_name() or issue.reported_by.email if issue.reported_by else ""
            items.append(
                {
                    "issue_id": issue.id,
                    "booking_id": booking.id,
                    "campaign_name": booking.campaign.name,
                    "site_name": site.name,
                    "unit_name": booking.media_unit.unit_code,
                    "reported_by": reporter,
                    "issue_type": issue.issue_type,
                    "description": issue.description,
                    "status": issue.status,
                    "priority": issue.priority,
                    "sla_status": issue.sla_status,
                    "first_response_due_at": issue.first_response_due_at,
                    "resolution_due_at": issue.resolution_due_at,
                    "image_url": build_public_media_url(issue.image, request=request),
                    "created_at": issue.created_at,
                }
            )
        return items
