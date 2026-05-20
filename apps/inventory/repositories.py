from core.repositories import BaseRepository
from core.roles import CLIENT
from apps.tenants.services import is_platform_super_admin, scope_queryset_to_tenant_path

from .models import MediaSite, MediaSiteImage, MediaUnit, MediaUnitImage, RateCard


class MediaSiteRepository(BaseRepository):
    model = MediaSite
    select_related = ("owner",)
    prefetch_related = ("images",)

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user)
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(units__bookings__campaign__client=user).distinct()
        return queryset.order_by("name")


class MediaUnitRepository(BaseRepository):
    model = MediaUnit
    select_related = ("site",)
    prefetch_related = ("images",)

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "site__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(bookings__campaign__client=user).distinct()
        return queryset.order_by("unit_code")

    def available_queryset(self, user=None):
        return self.get_queryset(user=user).filter(status=MediaUnit.Status.AVAILABLE)


class RateCardRepository(BaseRepository):
    model = RateCard
    select_related = ("unit", "unit__site")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "unit__site__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            return queryset.filter(unit__bookings__campaign__client=user).distinct()
        return queryset


class MediaSiteImageRepository(BaseRepository):
    model = MediaSiteImage
    select_related = ("site", "uploaded_by")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "site__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(site__units__bookings__campaign__client=user).distinct()
        return queryset.order_by("-is_primary", "-uploaded_at", "-id")


class MediaUnitImageRepository(BaseRepository):
    model = MediaUnitImage
    select_related = ("media_unit", "media_unit__site", "uploaded_by")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "media_unit__site__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(media_unit__bookings__campaign__client=user).distinct()
        return queryset.order_by("-is_primary", "-uploaded_at", "-id")
