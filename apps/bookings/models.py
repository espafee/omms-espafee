from django.db import models
from django.conf import settings

from apps.campaigns.models import Campaign
from apps.inventory.models import MediaUnit
from core.models import TimeStampedModel


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        LIVE = "live", "Live"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    campaign = models.ForeignKey(Campaign, related_name="bookings", on_delete=models.CASCADE)
    media_unit = models.ForeignKey(MediaUnit, related_name="bookings", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    booked_rate = models.DecimalField(max_digits=12, decimal_places=2)
    agreed_media_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    flex_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    installation_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "media_unit", "start_date", "end_date"],
                name="unique_booking_window_per_campaign_unit",
            )
        ]

    def __str__(self) -> str:
        return f"{self.campaign.code} / {self.media_unit.unit_code}"


class Assignment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    booking = models.ForeignKey(Booking, related_name="assignments", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="booking_assignments", on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_bookings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(fields=["booking", "user"], name="unique_assignment_per_booking_user"),
        ]

    def __str__(self) -> str:
        return f"{self.booking_id} assigned to {self.user_id}"
