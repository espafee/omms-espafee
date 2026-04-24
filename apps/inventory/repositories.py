from core.repositories import BaseRepository
from core.roles import CLIENT

from .models import MediaSite, MediaSiteImage, MediaUnit, MediaUnitImage, RateCard


class MediaSiteRepository(BaseRepository):
    model = MediaSite
    select_related = ("owner",)
    prefetch_related = ("images",)

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(units__bookings__campaign__client=user).distinct()
        return queryset.order_by("name")


class MediaUnitRepository(BaseRepository):
    model = MediaUnit
    select_related = ("site",)
    prefetch_related = ("images",)

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(bookings__campaign__client=user).distinct()
        return queryset.order_by("unit_code")

    def available_queryset(self, user=None):
        return self.get_queryset(user=user).filter(status=MediaUnit.Status.AVAILABLE)


class RateCardRepository(BaseRepository):
    model = RateCard
    select_related = ("unit", "unit__site")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            return queryset.filter(unit__bookings__campaign__client=user).distinct()
        return queryset


class MediaSiteImageRepository(BaseRepository):
    model = MediaSiteImage
    select_related = ("site", "uploaded_by")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(site__units__bookings__campaign__client=user).distinct()
        return queryset.order_by("-is_primary", "-uploaded_at", "-id")


class MediaUnitImageRepository(BaseRepository):
    model = MediaUnitImage
    select_related = ("media_unit", "media_unit__site", "uploaded_by")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(media_unit__bookings__campaign__client=user).distinct()
        return queryset.order_by("-is_primary", "-uploaded_at", "-id")
