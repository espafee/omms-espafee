from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ProviderImageModel(models.Model):
    class Provider(models.TextChoices):
        R2 = "r2", "Cloudflare R2"
        CLOUDINARY = "cloudinary", "Cloudinary"

    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.R2, db_index=True)
    provider_asset_id = models.CharField(max_length=255, blank=True)
    provider_public_id = models.CharField(max_length=500, blank=True)
    provider_version = models.CharField(max_length=50, blank=True)
    secure_url = models.URLField(blank=True, max_length=1000)
    resource_type = models.CharField(max_length=40, blank=True)
    format = models.CharField(max_length=30, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    bytes = models.PositiveIntegerField(null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def image_url(self, *, request=None, variant="original"):
        from core.media_storage import get_media_storage_provider_for_record

        return get_media_storage_provider_for_record(self).build_delivery_url(self, request=request, variant=variant)
