from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from core.services import BaseService
from rest_framework.exceptions import ValidationError

from apps.notifications.services import trigger_campaign_booked_notification

from .models import Assignment, Booking
from .repositories import BookingRepository

SUMMARY_DECIMAL_FIELD = DecimalField(max_digits=14, decimal_places=2)


class BookingService(BaseService):
    repository_class = BookingRepository

    def _validate_dates(self, start_date, end_date):
        if end_date < start_date:
            raise ValidationError("End date must be greater than or equal to start date.")

    def _validate_availability(self, media_unit, start_date, end_date, exclude_id=None):
        overlap_exists = self.repository.get_overlapping_bookings(
            media_unit=media_unit,
            start_date=start_date,
            end_date=end_date,
            exclude_id=exclude_id,
        ).exists()
        if overlap_exists:
            raise ValidationError("The selected media unit is already booked for the given date range.")

    def create(self, actor=None, **validated_data):
        assigned_user = validated_data.pop("assigned_user", None)
        self._validate_dates(validated_data["start_date"], validated_data["end_date"])
        self._validate_availability(
            media_unit=validated_data["media_unit"],
            start_date=validated_data["start_date"],
            end_date=validated_data["end_date"],
        )
        booking = super().create(actor=actor, **validated_data)
        if assigned_user:
            self._set_assignment(booking=booking, assigned_user=assigned_user, actor=actor)
        trigger_campaign_booked_notification(booking, actor=actor)
        return booking

    def update(self, instance, actor=None, **validated_data):
        assignment_was_provided = "assigned_user" in validated_data
        assigned_user = validated_data.pop("assigned_user", None)
        start_date = validated_data.get("start_date", instance.start_date)
        end_date = validated_data.get("end_date", instance.end_date)
        media_unit = validated_data.get("media_unit", instance.media_unit)

        self._validate_dates(start_date, end_date)
        self._validate_availability(
            media_unit=media_unit,
            start_date=start_date,
            end_date=end_date,
            exclude_id=instance.id,
        )
        booking = super().update(instance, actor=actor, **validated_data)
        if assignment_was_provided:
            self._set_assignment(booking=booking, assigned_user=assigned_user, actor=actor)
        return booking

    def _set_assignment(self, booking, assigned_user, actor=None):
        # Keep one current assignee for now while the model supports future multi-assignment.
        booking.assignments.exclude(user=assigned_user).delete()
        if assigned_user is None:
            booking.assignments.all().delete()
            return
        Assignment.objects.update_or_create(
            booking=booking,
            user=assigned_user,
            defaults={"assigned_by": actor, "status": Assignment.Status.PENDING},
        )

    def get_summary(self, user=None):
        queryset = self.get_queryset(user=user)
        return queryset.aggregate(
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
