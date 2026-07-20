from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.tenants.services import resolve_write_tenant, require_same_tenant
from core.media_storage import (
    apply_uploaded_metadata,
    build_storage_folder,
    get_media_storage_provider,
    get_media_storage_provider_for_record,
)
from core.services import BaseService

from .repositories import (
    MediaSiteImageRepository,
    MediaSiteRepository,
    MediaUnitImageRepository,
    MediaUnitRepository,
    RateCardRepository,
)


class MediaSiteService(BaseService):
    repository_class = MediaSiteRepository

    ACTIVE_BOOKING_STATUSES = (
        Booking.Status.PENDING,
        Booking.Status.CONFIRMED,
        Booking.Status.LIVE,
    )

    def create(self, actor=None, **validated_data):
        if actor and not validated_data.get("owner"):
            validated_data["owner"] = actor
        if actor and "tenant" not in validated_data:
            validated_data["tenant"] = resolve_write_tenant(actor)
        elif actor:
            validated_data["tenant"] = resolve_write_tenant(actor, validated_data.get("tenant"))
        instance = super().create(actor=actor, **validated_data)
        self._apply_manual_location_metadata(
            instance,
            actor=actor,
            latitude_changed=instance.latitude is not None,
            longitude_changed=instance.longitude is not None,
        )
        return instance

    def update(self, instance, actor=None, **validated_data):
        latitude_changed = "latitude" in validated_data and validated_data.get("latitude") != instance.latitude
        longitude_changed = "longitude" in validated_data and validated_data.get("longitude") != instance.longitude
        instance = super().update(instance, actor=actor, **validated_data)
        self._apply_manual_location_metadata(
            instance,
            actor=actor,
            latitude_changed=latitude_changed,
            longitude_changed=longitude_changed,
        )
        return instance

    def _apply_manual_location_metadata(self, instance, *, actor=None, latitude_changed=False, longitude_changed=False):
        if not (latitude_changed or longitude_changed):
            return

        if instance.latitude is None or instance.longitude is None:
            instance.location_status = instance.LocationStatus.UNVERIFIED
            instance.location_source = ""
            instance.location_verified_at = None
            instance.location_verified_by = None
        else:
            is_admin = bool(
                actor
                and (
                    getattr(actor, "is_staff", False)
                    or getattr(actor, "is_superuser", False)
                    or getattr(actor, "role", "") == "admin"
                )
            )
            instance.location_status = (
                instance.LocationStatus.VERIFIED if is_admin else instance.LocationStatus.PROVISIONAL
            )
            instance.location_source = (
                instance.LocationSource.ADMIN_VERIFIED if is_admin else instance.LocationSource.MANUAL
            )
            instance.location_verified_at = timezone.now() if is_admin else None
            instance.location_verified_by = actor if is_admin else None

        instance.save(
            update_fields=[
                "location_status",
                "location_source",
                "location_verified_at",
                "location_verified_by",
                "updated_at",
            ]
        )

    def delete(self, instance, actor=None):
        has_active_bookings = instance.units.filter(
            bookings__status__in=self.ACTIVE_BOOKING_STATUSES
        ).exists()
        if has_active_bookings:
            raise ValidationError("This site cannot be deleted because it has active bookings linked to its media units.")
        return super().delete(instance, actor=actor)


class MediaUnitService(BaseService):
    repository_class = MediaUnitRepository

    def get_available_units(self, user=None):
        return self.repository.available_queryset(user=user)

    def create(self, actor=None, **validated_data):
        if actor:
            require_same_tenant(actor, validated_data["site"].tenant, message="You can only create units for your own company sites.")
        return super().create(actor=actor, **validated_data)


class RateCardService(BaseService):
    repository_class = RateCardRepository

    def create(self, actor=None, **validated_data):
        if actor:
            require_same_tenant(actor, validated_data["unit"].site.tenant, message="You can only create rates for your own company units.")
        return super().create(actor=actor, **validated_data)


class MediaSiteImageService(BaseService):
    repository_class = MediaSiteImageRepository

    def create(self, actor=None, **validated_data):
        if actor:
            require_same_tenant(actor, validated_data["site"].tenant, message="You can only upload images for your own company sites.")
        if actor and "uploaded_by" not in validated_data:
            validated_data["uploaded_by"] = actor
        if not validated_data.get("is_primary") and not validated_data["site"].images.exists():
            validated_data["is_primary"] = True
        provider = get_media_storage_provider()
        if provider.provider_name == "cloudinary":
            image = validated_data.pop("image", None)
            folder = build_storage_folder(
                tenant_id=validated_data["site"].tenant_id,
                entity_kind="locations",
                entity_id=validated_data["site"].id,
            )
            uploaded = provider.upload_image(
                image,
                folder=folder,
                metadata={"tenant_id": validated_data["site"].tenant_id, "site_id": validated_data["site"].id},
            )
            try:
                instance = self.repository.model(**validated_data)
                apply_uploaded_metadata(instance, uploaded)
                instance.save()
                return instance
            except Exception:
                provider.delete_image(type("UploadedRecord", (), {"provider_public_id": uploaded.provider_public_id})())
                raise
        return super().create(actor=actor, **validated_data)

    def update(self, instance, actor=None, **validated_data):
        new_image = validated_data.get("image")
        provider = get_media_storage_provider()
        if new_image and provider.provider_name == "cloudinary":
            old_provider = instance.provider
            old_public_id = instance.provider_public_id
            validated_data.pop("image")
            uploaded = provider.upload_image(
                new_image,
                folder=build_storage_folder(
                    tenant_id=instance.site.tenant_id,
                    entity_kind="locations",
                    entity_id=instance.site_id,
                ),
                metadata={"tenant_id": instance.site.tenant_id, "site_id": instance.site_id},
            )
            try:
                for key, value in validated_data.items():
                    setattr(instance, key, value)
                instance.image = None
                apply_uploaded_metadata(instance, uploaded)
                instance.save()
            except Exception:
                provider.delete_image(type("UploadedRecord", (), {"provider_public_id": uploaded.provider_public_id})())
                raise
            if old_provider == instance.Provider.CLOUDINARY and old_public_id:
                provider.delete_image(type("OldRecord", (), {"provider_public_id": old_public_id})())
            return instance
        return super().update(instance, actor=actor, **validated_data)

    def delete(self, instance, actor=None):
        if instance.provider == instance.Provider.CLOUDINARY:
            get_media_storage_provider_for_record(instance).delete_image(instance)
        return super().delete(instance, actor=actor)


class MediaUnitImageService(BaseService):
    repository_class = MediaUnitImageRepository

    def create(self, actor=None, **validated_data):
        if actor:
            require_same_tenant(actor, validated_data["media_unit"].site.tenant, message="You can only upload images for your own company units.")
        if actor and "uploaded_by" not in validated_data:
            validated_data["uploaded_by"] = actor
        if not validated_data.get("is_primary") and not validated_data["media_unit"].images.exists():
            validated_data["is_primary"] = True
        provider = get_media_storage_provider()
        if provider.provider_name == "cloudinary":
            image = validated_data.pop("image", None)
            unit = validated_data["media_unit"]
            folder = build_storage_folder(
                tenant_id=unit.site.tenant_id,
                entity_kind="advertising-units",
                entity_id=unit.id,
            )
            uploaded = provider.upload_image(
                image,
                folder=folder,
                metadata={"tenant_id": unit.site.tenant_id, "media_unit_id": unit.id},
            )
            try:
                instance = self.repository.model(**validated_data)
                apply_uploaded_metadata(instance, uploaded)
                instance.save()
                return instance
            except Exception:
                provider.delete_image(type("UploadedRecord", (), {"provider_public_id": uploaded.provider_public_id})())
                raise
        return super().create(actor=actor, **validated_data)

    def update(self, instance, actor=None, **validated_data):
        new_image = validated_data.get("image")
        provider = get_media_storage_provider()
        if new_image and provider.provider_name == "cloudinary":
            old_provider = instance.provider
            old_public_id = instance.provider_public_id
            validated_data.pop("image")
            uploaded = provider.upload_image(
                new_image,
                folder=build_storage_folder(
                    tenant_id=instance.media_unit.site.tenant_id,
                    entity_kind="advertising-units",
                    entity_id=instance.media_unit_id,
                ),
                metadata={"tenant_id": instance.media_unit.site.tenant_id, "media_unit_id": instance.media_unit_id},
            )
            try:
                for key, value in validated_data.items():
                    setattr(instance, key, value)
                instance.image = None
                apply_uploaded_metadata(instance, uploaded)
                instance.save()
            except Exception:
                provider.delete_image(type("UploadedRecord", (), {"provider_public_id": uploaded.provider_public_id})())
                raise
            if old_provider == instance.Provider.CLOUDINARY and old_public_id:
                provider.delete_image(type("OldRecord", (), {"provider_public_id": old_public_id})())
            return instance
        return super().update(instance, actor=actor, **validated_data)

    def delete(self, instance, actor=None):
        if instance.provider == instance.Provider.CLOUDINARY:
            get_media_storage_provider_for_record(instance).delete_image(instance)
        return super().delete(instance, actor=actor)
