import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.bookings.models import Assignment, Booking
from core.images import compress_field_image
from core.models import TimeStampedModel


def issue_image_upload_to(instance, filename):
    return f"issues/{instance.booking_id}/{filename}"


class Issue(TimeStampedModel):
    class ReporterType(models.TextChoices):
        FIELD_STAFF = "field_staff", "Field Staff"
        CLIENT = "client", "Client"

    class IssueType(models.TextChoices):
        DAMAGE = "damage", "Damage"
        MISSING = "missing", "Missing"
        WRONG = "wrong", "Wrong"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        REPORTED = "reported", "Reported"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class SlaStatus(models.TextChoices):
        ON_TRACK = "on_track", "On Track"
        AT_RISK = "at_risk", "At Risk"
        BREACHED = "breached", "Breached"

    booking = models.ForeignKey(Booking, related_name="issues", on_delete=models.CASCADE)
    assignment = models.ForeignKey(
        Assignment,
        related_name="issues",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reported_issues",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reporter_type = models.CharField(max_length=20, choices=ReporterType.choices, default=ReporterType.FIELD_STAFF)
    issue_type = models.CharField(max_length=20, choices=IssueType.choices)
    description = models.TextField()
    image = models.ImageField(upload_to=issue_image_upload_to, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    contact = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    priority_reason = models.TextField(blank=True)
    first_response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    sla_status = models.CharField(max_length=20, choices=SlaStatus.choices, default=SlaStatus.ON_TRACK)
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="escalated_issues",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    escalation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "status"]),
            models.Index(fields=["priority", "status"]),
            models.Index(fields=["sla_status", "resolution_due_at"]),
        ]

    def save(self, *args, **kwargs):
        from .services import prepare_issue_for_save

        is_create = self._state.adding
        if self.status == self.Status.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
        if self.status != self.Status.RESOLVED:
            self.resolved_at = None
        prepare_issue_for_save(self, is_create=is_create)
        compress_field_image(self.image)
        super().save(*args, **kwargs)
        if is_create:
            IssueEvent.objects.create(
                issue=self,
                actor=self.reported_by,
                event_type=IssueEvent.EventType.REPORTED,
                message="Issue reported.",
                metadata={"priority": self.priority, "sla_status": self.sla_status},
            )
            try:
                from apps.observability.services import record_audit_event

                record_audit_event(
                    event_type="issue.reported",
                    entity_type="issue",
                    entity_id=self.id,
                    actor=self.reported_by,
                    severity="warning" if self.priority in {self.Priority.HIGH, self.Priority.CRITICAL} else "info",
                    summary="Public or field issue reported.",
                    metadata={"priority": self.priority, "reporter_type": self.reporter_type},
                    campaign_reference=getattr(self.booking.campaign, "code", ""),
                )
            except Exception:
                pass
            try:
                from apps.notifications.services import trigger_issue_reported_notification

                trigger_issue_reported_notification(self, actor=self.reported_by)
            except Exception:
                pass
            try:
                from .services import should_auto_escalate_issue, escalate_issue

                if should_auto_escalate_issue(self):
                    escalate_issue(self, actor=self.reported_by, reason="High priority issue requires escalation.", auto=True)
            except Exception:
                pass

    def __str__(self) -> str:
        return f"{self.get_issue_type_display()} issue for booking {self.booking_id}"


class IssueEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        REPORTED = "reported", "Reported"
        ESCALATED = "escalated", "Escalated"
        TASK_ASSIGNED = "task_assigned", "Task Assigned"
        AUTO_RESOLVED = "auto_resolved", "Auto Resolved"

    issue = models.ForeignKey(Issue, related_name="events", on_delete=models.CASCADE)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="issue_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    message = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["issue", "event_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.issue_id} - {self.event_type}"


def issue_report_token_default():
    return secrets.token_urlsafe(32)


class IssueReportToken(TimeStampedModel):
    booking = models.ForeignKey(Booking, related_name="issue_report_tokens", on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True, default=issue_report_token_default)
    expires_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_issue_report_tokens",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["token", "expires_at"]),
        ]

    def is_valid(self) -> bool:
        return self.expires_at > timezone.now()

    def __str__(self) -> str:
        return f"Issue report token for booking {self.booking_id}"


class IssueTask(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    issue = models.ForeignKey(Issue, related_name="tasks", on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="issue_tasks",
        on_delete=models.CASCADE,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_issue_tasks",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    due_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["issue"],
                condition=models.Q(status__in=["pending", "in_progress"]),
                name="unique_active_task_per_issue",
            ),
        ]
        indexes = [
            models.Index(fields=["assigned_to", "status", "due_at"]),
            models.Index(fields=["issue", "status"]),
        ]

    def save(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        if self.status != self.Status.COMPLETED:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Issue task {self.pk or 'new'} for issue {self.issue_id}"
