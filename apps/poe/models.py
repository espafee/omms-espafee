from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.bookings.models import Booking
from core.models import TimeStampedModel


def poe_media_upload_to(instance, filename):
    return f"poe/{instance.poe_record_id}/{filename}"


class ProofOfExecution(TimeStampedModel):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        SUSPICIOUS = "suspicious", "Suspicious"
        REJECTED = "rejected", "Rejected"

    booking = models.ForeignKey(Booking, related_name="poe_records", on_delete=models.CASCADE)
    executed_on = models.DateField()
    captured_at = models.DateTimeField(default=timezone.now)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="verified_poe_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verification_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"POE {self.booking_id} - {self.executed_on}"


class ProofOfExecutionMedia(TimeStampedModel):
    poe_record = models.ForeignKey(
        ProofOfExecution,
        related_name="media_items",
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to=poe_media_upload_to, blank=True, null=True)
    media_url = models.URLField(blank=True)
    media_type = models.CharField(max_length=20, default="image")
    captured_at = models.DateTimeField(default=timezone.now)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="captured_poe_media",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-captured_at", "-created_at"]

    def __str__(self) -> str:
        return self.media_url or (self.image.name if self.image else f"POE media {self.pk}")


class ProofOfExecutionVerificationLog(TimeStampedModel):
    poe_record = models.ForeignKey(
        ProofOfExecution,
        related_name="verification_logs",
        on_delete=models.CASCADE,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="poe_verification_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status_before = models.CharField(max_length=20, blank=True)
    status_after = models.CharField(max_length=20)
    verification_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    distance_meters = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    threshold_meters = models.DecimalField(max_digits=10, decimal_places=2, default=250)
    notes = models.TextField(blank=True)
    result_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"POE verification log {self.pk} for {self.poe_record_id}"
