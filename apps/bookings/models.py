from django.db import models

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
