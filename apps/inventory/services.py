from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
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


class RateCardService(BaseService):
    repository_class = RateCardRepository


class MediaSiteImageService(BaseService):
    repository_class = MediaSiteImageRepository

    def create(self, actor=None, **validated_data):
        if actor and "uploaded_by" not in validated_data:
            validated_data["uploaded_by"] = actor
        if not validated_data.get("is_primary") and not validated_data["site"].images.exists():
            validated_data["is_primary"] = True
        return super().create(actor=actor, **validated_data)


class MediaUnitImageService(BaseService):
    repository_class = MediaUnitImageRepository

    def create(self, actor=None, **validated_data):
        if actor and "uploaded_by" not in validated_data:
            validated_data["uploaded_by"] = actor
        if not validated_data.get("is_primary") and not validated_data["media_unit"].images.exists():
            validated_data["is_primary"] = True
        return super().create(actor=actor, **validated_data)
