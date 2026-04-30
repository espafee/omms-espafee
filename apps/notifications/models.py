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
    recipient_email = models.EmailField(blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.notification_type} -> {self.recipient_email or 'no-recipient'} ({self.status})"
