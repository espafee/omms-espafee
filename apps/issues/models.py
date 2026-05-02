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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "status"]),
            models.Index(fields=["priority", "status"]),
        ]

    def save(self, *args, **kwargs):
        if self.status == self.Status.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
        if self.status != self.Status.RESOLVED:
            self.resolved_at = None
        compress_field_image(self.image)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_issue_type_display()} issue for booking {self.booking_id}"
