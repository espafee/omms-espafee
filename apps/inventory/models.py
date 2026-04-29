from django.conf import settings
from django.db import models, transaction
from django.db.models import Q

from core.models import TimeStampedModel
from core.images import compress_field_image


def site_image_upload_to(instance, filename):
    return f"inventory/sites/{instance.site_id}/{filename}"


def unit_image_upload_to(instance, filename):
    return f"inventory/units/{instance.media_unit_id}/{filename}"


class MediaSite(TimeStampedModel):
    class SiteType(models.TextChoices):
        BILLBOARD = "billboard", "Billboard"
        TRANSIT = "transit", "Transit"
        STREET_FURNITURE = "street_furniture", "Street Furniture"
        DIGITAL = "digital", "Digital"

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    site_type = models.CharField(max_length=30, choices=SiteType.choices)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_sites",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    @property
    def primary_image_object(self):
        return self.images.filter(is_primary=True).first() or self.images.order_by("uploaded_at", "id").first()

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class MediaUnit(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"

    class SiteType(models.TextChoices):
        SINGLE_SIDE = "single_side", "Single Side"
        BOTH_SIDE = "both_side", "Both Side"

    site = models.ForeignKey(MediaSite, related_name="units", on_delete=models.CASCADE)
    unit_code = models.CharField(max_length=50, unique=True)
    face_count = models.PositiveIntegerField(default=1)
    width = models.DecimalField(max_digits=8, decimal_places=2)
    height = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_illuminated = models.BooleanField(default=False)
    monthly_rate = models.DecimalField(max_digits=12, decimal_places=2)
    facing_direction = models.CharField(max_length=150, blank=True)
    site_type = models.CharField(max_length=40, choices=SiteType.choices, blank=True)

    @property
    def primary_image_object(self):
        return self.images.filter(is_primary=True).first() or self.images.order_by("uploaded_at", "id").first()

    def __str__(self) -> str:
        return self.unit_code


class RateCard(TimeStampedModel):
    unit = models.ForeignKey(MediaUnit, related_name="rate_cards", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    base_rate = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return f"{self.unit.unit_code} ({self.start_date} - {self.end_date})"


class MediaSiteImage(TimeStampedModel):
    site = models.ForeignKey(MediaSite, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=site_image_upload_to)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="uploaded_site_images",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-uploaded_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["site"],
                condition=Q(is_primary=True),
                name="unique_primary_site_image",
            )
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_primary:
                self.site.images.exclude(pk=self.pk).filter(is_primary=True).update(is_primary=False)
            compress_field_image(self.image)
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.site.code} image {self.pk}"


class MediaUnitImage(TimeStampedModel):
    media_unit = models.ForeignKey(MediaUnit, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=unit_image_upload_to)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="uploaded_unit_images",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-uploaded_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["media_unit"],
                condition=Q(is_primary=True),
                name="unique_primary_media_unit_image",
            )
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_primary:
                self.media_unit.images.exclude(pk=self.pk).filter(is_primary=True).update(is_primary=False)
            compress_field_image(self.image)
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.media_unit.unit_code} image {self.pk}"
