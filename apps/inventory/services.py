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
        return super().create(actor=actor, **validated_data)

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
