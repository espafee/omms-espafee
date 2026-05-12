from django.conf import settings
from django.db import models

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia
from core.models import TimeStampedModel


class EmailNotificationLog(TimeStampedModel):
    class NotificationType(models.TextChoices):
        CAMPAIGN_BOOKED = "campaign_booked", "Campaign Booked"
        POE_UPLOADED = "poe_uploaded", "POE Uploaded"
        INVOICE_ISSUED = "invoice_issued", "Invoice Issued"
        PAYMENT_RECORDED = "payment_recorded", "Payment Recorded"
        SUSPICIOUS_POE = "suspicious_poe", "Suspicious POE"
        ISSUE_REPORTED = "issue_reported", "Issue Reported"
        ISSUE_ESCALATED = "issue_escalated", "Issue Escalated"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    event_key = models.CharField(max_length=255, unique=True, db_index=True)
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    campaign = models.ForeignKey(
        Campaign,
        related_name="email_notification_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    booking = models.ForeignKey(
        Booking,
        related_name="email_notification_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    poe_record = models.ForeignKey(
        ProofOfExecution,
        related_name="email_notification_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    poe_media = models.ForeignKey(
        ProofOfExecutionMedia,
        related_name="email_notification_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    issue = models.ForeignKey(
        "issues.Issue",
        related_name="email_notification_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    recipient_email = models.EmailField(blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.notification_type} -> {self.recipient_email or 'no-recipient'} ({self.status})"


class NotificationPreference(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notification_preferences",
        on_delete=models.CASCADE,
    )
    notification_type = models.CharField(max_length=30, choices=EmailNotificationLog.NotificationType.choices)
    email_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "notification_type")
        ordering = ["user_id", "notification_type"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.notification_type}: {'email' if self.email_enabled else 'muted'}"


class Notification(TimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    class DeliveryStatus(models.TextChoices):
        INTERNAL = "internal", "Internal"
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="notifications",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    recipient_role = models.CharField(max_length=30, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, blank=True)
    event_type = models.CharField(max_length=30, choices=EmailNotificationLog.NotificationType.choices, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.INTERNAL)
    retry_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["recipient_role", "is_read", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        target = self.recipient.email if self.recipient else self.recipient_role or "team"
        return f"{self.title} -> {target}"
