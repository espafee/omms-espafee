from core.repositories import BaseRepository
from core.roles import CLIENT

from .models import Booking


class BookingRepository(BaseRepository):
    model = Booking
    select_related = (
        "campaign",
        "campaign__client",
        "media_unit",
        "media_unit__site",
    )

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            return queryset.filter(campaign__client=user)
        return queryset

    def get_overlapping_bookings(self, media_unit, start_date, end_date, exclude_id=None):
        queryset = self.get_queryset().filter(
            media_unit=media_unit,
            start_date__lte=end_date,
            end_date__gte=start_date,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.LIVE],
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset
