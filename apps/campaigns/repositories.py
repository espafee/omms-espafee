from django.db.models import Prefetch

from apps.bookings.models import Booking
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia
from core.repositories import BaseRepository
from core.roles import CLIENT
from apps.tenants.services import is_platform_super_admin, scope_queryset_to_tenant_path

from .models import Campaign, CampaignAccessToken, CampaignAsset


class CampaignRepository(BaseRepository):
    model = Campaign
    select_related = ("client", "account_manager")
    prefetch_related = ("assets",)

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user)
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(client=user)
        return queryset.order_by("-created_at")


class CampaignAssetRepository(BaseRepository):
    model = CampaignAsset
    select_related = ("campaign",)

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(campaign__client=user)
        return queryset.order_by("-created_at")

class CampaignAccessTokenRepository(BaseRepository):
    model = CampaignAccessToken
    select_related = ("campaign", "created_by", "revoked_by")

    def scope_queryset(self, queryset, user=None):
        return scope_queryset_to_tenant_path(queryset, user, "campaign__tenant")

    def get_public_campaign_queryset(self):
        return Campaign.objects.select_related("client").prefetch_related(
            Prefetch("assets", queryset=CampaignAsset.objects.filter(is_approved=True).order_by("-created_at")),
            Prefetch(
                "bookings",
                queryset=Booking.objects.select_related("media_unit", "media_unit__site").prefetch_related(
                    Prefetch(
                        "poe_records",
                        queryset=ProofOfExecution.objects.prefetch_related(
                            Prefetch(
                                "media_items",
                                queryset=ProofOfExecutionMedia.objects.order_by("-captured_at", "-created_at"),
                            )
                        ).order_by("-captured_at", "-created_at"),
                    )
                ).order_by("-start_date", "-created_at"),
            ),
        )
