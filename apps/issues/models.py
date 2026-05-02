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

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "status"]),
            models.Index(fields=["priority", "status"]),
            models.Index(fields=["sla_status", "resolution_due_at"]),
        ]

    def save(self, *args, **kwargs):
        from .services import prepare_issue_for_save

        if self.status == self.Status.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
        if self.status != self.Status.RESOLVED:
            self.resolved_at = None
        prepare_issue_for_save(self, is_create=self._state.adding)
        compress_field_image(self.image)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_issue_type_display()} issue for booking {self.booking_id}"


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
