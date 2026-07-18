from decimal import Decimal

from django.db import IntegrityError
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.conf import settings
from django.core.cache import cache
from core.services import BaseService
from rest_framework.exceptions import ValidationError

from apps.notifications.services import trigger_campaign_booked_notification
from apps.tenants.services import require_same_tenant

from .models import Assignment, Booking
from .repositories import BookingRepository

SUMMARY_DECIMAL_FIELD = DecimalField(max_digits=14, decimal_places=2)


class BookingService(BaseService):
    repository_class = BookingRepository

    def _validate_dates(self, start_date, end_date):
        if end_date < start_date:
            raise ValidationError("End date must be greater than or equal to start date.")

    def _validate_availability(self, media_unit, start_date, end_date, exclude_id=None):
        from apps.planner.services import InventoryAvailabilityService

        InventoryAvailabilityService().assert_bookable(
            media_unit,
            start_date=start_date,
            end_date=end_date,
            exclude_booking_id=exclude_id,
        )

    def _validate_unique_booking_window(self, campaign, media_unit, start_date, end_date, exclude_id=None):
        duplicate_exists = Booking.objects.filter(
            campaign=campaign,
            media_unit=media_unit,
            start_date=start_date,
            end_date=end_date,
        )
        if exclude_id:
            duplicate_exists = duplicate_exists.exclude(id=exclude_id)
        if duplicate_exists.exists():
            raise ValidationError("This campaign already has a booking for the selected media unit and date range.")

    def create(self, actor=None, **validated_data):
        assigned_user = validated_data.pop("assigned_user", None)
        if actor:
            require_same_tenant(actor, validated_data["campaign"].tenant, message="You can only create bookings for your own company campaigns.")
        if validated_data["campaign"].tenant_id != validated_data["media_unit"].site.tenant_id:
            raise ValidationError("Campaign and media unit must belong to the same tenant.")
        if assigned_user and assigned_user.tenant_id != validated_data["campaign"].tenant_id:
            raise ValidationError("Assigned user must belong to the campaign tenant.")
        self._validate_dates(validated_data["start_date"], validated_data["end_date"])
        self._validate_unique_booking_window(
            campaign=validated_data["campaign"],
            media_unit=validated_data["media_unit"],
            start_date=validated_data["start_date"],
            end_date=validated_data["end_date"],
        )
        self._validate_availability(
            media_unit=validated_data["media_unit"],
            start_date=validated_data["start_date"],
            end_date=validated_data["end_date"],
        )
        if not validated_data.get("agreed_media_cost"):
            validated_data["agreed_media_cost"] = validated_data["booked_rate"]
        try:
            booking = super().create(actor=actor, **validated_data)
        except IntegrityError as exc:
            if "unique_booking_window_per_campaign_unit" in str(exc):
                raise ValidationError(
                    "This campaign already has a booking for the selected media unit and date range."
                ) from exc
            raise
        if assigned_user:
            self._set_assignment(booking=booking, assigned_user=assigned_user, actor=actor)
        self._invalidate_dashboard_cache()
        trigger_campaign_booked_notification(booking, actor=actor)
        return booking

    def update(self, instance, actor=None, **validated_data):
        assignment_was_provided = "assigned_user" in validated_data
        assigned_user = validated_data.pop("assigned_user", None)
        start_date = validated_data.get("start_date", instance.start_date)
        end_date = validated_data.get("end_date", instance.end_date)
        media_unit = validated_data.get("media_unit", instance.media_unit)
        campaign = validated_data.get("campaign", instance.campaign)
        if actor:
            require_same_tenant(actor, campaign.tenant, message="You can only update bookings for your own company campaigns.")
        if campaign.tenant_id != media_unit.site.tenant_id:
            raise ValidationError("Campaign and media unit must belong to the same tenant.")
        if assigned_user and assigned_user.tenant_id != campaign.tenant_id:
            raise ValidationError("Assigned user must belong to the campaign tenant.")

        self._validate_dates(start_date, end_date)
        self._validate_unique_booking_window(
            campaign=campaign,
            media_unit=media_unit,
            start_date=start_date,
            end_date=end_date,
            exclude_id=instance.id,
        )
        self._validate_availability(
            media_unit=media_unit,
            start_date=start_date,
            end_date=end_date,
            exclude_id=instance.id,
        )
        if "agreed_media_cost" not in validated_data and not instance.agreed_media_cost:
            validated_data["agreed_media_cost"] = validated_data.get("booked_rate", instance.booked_rate)
        try:
            booking = super().update(instance, actor=actor, **validated_data)
        except IntegrityError as exc:
            if "unique_booking_window_per_campaign_unit" in str(exc):
                raise ValidationError(
                    "This campaign already has a booking for the selected media unit and date range."
                ) from exc
            raise
        if assignment_was_provided:
            self._set_assignment(booking=booking, assigned_user=assigned_user, actor=actor)
        self._invalidate_dashboard_cache()
        return booking

    def _set_assignment(self, booking, assigned_user, actor=None):
        if assigned_user is None:
            booking.assignments.exclude(status=Assignment.Status.CANCELLED).update(status=Assignment.Status.CANCELLED)
            return
        # Keep one current assignee for now while preserving cancelled assignment history.
        booking.assignments.exclude(user=assigned_user).exclude(status=Assignment.Status.CANCELLED).update(
            status=Assignment.Status.CANCELLED
        )
        Assignment.objects.update_or_create(
            booking=booking,
            user=assigned_user,
            defaults={"assigned_by": actor, "status": Assignment.Status.PENDING},
        )

    def get_summary(self, user=None):
        cache_key = f"dashboard:bookings:{self._dashboard_cache_version()}:{getattr(user, 'id', 'anon')}:{getattr(user, 'role', '')}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        queryset = self.get_queryset(user=user)
        summary = queryset.aggregate(
            total_bookings=Count("id"),
            pending_bookings=Count("id", filter=Q(status=Booking.Status.PENDING)),
            confirmed_bookings=Count("id", filter=Q(status=Booking.Status.CONFIRMED)),
            live_bookings=Count("id", filter=Q(status=Booking.Status.LIVE)),
            completed_bookings=Count("id", filter=Q(status=Booking.Status.COMPLETED)),
            cancelled_bookings=Count("id", filter=Q(status=Booking.Status.CANCELLED)),
            unique_media_units=Count("media_unit", distinct=True),
            total_booked_value=Coalesce(Sum("booked_rate"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD),
            live_booked_value=Coalesce(
                Sum("booked_rate", filter=Q(status=Booking.Status.LIVE)),
                Decimal("0.00"),
                output_field=SUMMARY_DECIMAL_FIELD,
            ),
        )
        cache.set(cache_key, summary, getattr(settings, "OMMS_DASHBOARD_CACHE_SECONDS", 60))
        return summary

    def _dashboard_cache_version(self):
        try:
            from apps.observability.services import get_dashboard_cache_version

            return get_dashboard_cache_version()
        except Exception:
            return 1

    def _invalidate_dashboard_cache(self):
        try:
            from apps.observability.services import bump_dashboard_cache_version

            bump_dashboard_cache_version()
        except Exception:
            pass
