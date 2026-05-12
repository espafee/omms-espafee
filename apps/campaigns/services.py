from datetime import datetime, time
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.bookings.models import Booking
from core.services import BaseService

from .models import Campaign, CampaignAccessToken
from .repositories import CampaignAccessTokenRepository, CampaignAssetRepository, CampaignRepository

SUMMARY_DECIMAL_FIELD = DecimalField(max_digits=14, decimal_places=2)


class CampaignService(BaseService):
    repository_class = CampaignRepository

    def get_active_campaigns(self):
        return self.get_queryset().filter(status="active")

    def get_summary(self, user=None):
        cache_key = f"dashboard:campaigns:{self._dashboard_cache_version()}:{getattr(user, 'id', 'anon')}:{getattr(user, 'role', '')}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        queryset = self.get_queryset(user=user)
        summary = queryset.aggregate(
            total_campaigns=Count("id"),
            active_campaigns=Count("id", filter=Q(status=Campaign.Status.ACTIVE)),
            draft_campaigns=Count("id", filter=Q(status=Campaign.Status.DRAFT)),
            completed_campaigns=Count("id", filter=Q(status=Campaign.Status.COMPLETED)),
            total_budget=Coalesce(Sum("budget"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD),
            active_budget=Coalesce(
                Sum("budget", filter=Q(status=Campaign.Status.ACTIVE)),
                Decimal("0.00"),
                output_field=SUMMARY_DECIMAL_FIELD,
            ),
            total_bookings=Count("bookings", distinct=True),
            live_bookings=Count("bookings", filter=Q(bookings__status=Booking.Status.LIVE), distinct=True),
            approved_assets=Count("assets", filter=Q(assets__is_approved=True), distinct=True),
        )
        cache.set(cache_key, summary, getattr(settings, "OMMS_DASHBOARD_CACHE_SECONDS", 60))
        return summary

    def create(self, actor=None, **validated_data):
        campaign = super().create(actor=actor, **validated_data)
        self._invalidate_dashboard_cache()
        return campaign

    def update(self, instance, actor=None, **validated_data):
        campaign = super().update(instance, actor=actor, **validated_data)
        self._invalidate_dashboard_cache()
        return campaign

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


class CampaignAssetService(BaseService):
    repository_class = CampaignAssetRepository


class PublicCampaignAccessError(Exception):
    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CampaignAccessTokenService(BaseService):
    repository_class = CampaignAccessTokenRepository

    def get_active_token(self, campaign):
        tokens = self.get_queryset().filter(campaign=campaign).order_by("-created_at")
        for access_token in tokens:
            if access_token.is_available():
                return access_token
        return None

    def create_token(self, *, campaign, actor=None, expires_at=None):
        existing = self.get_active_token(campaign)
        if existing and existing.token_value:
            return existing, existing.token_value, False

        if existing and not existing.token_value:
            existing.revoke(actor=actor)

        created, raw_token = CampaignAccessToken.create_with_token(
            campaign=campaign,
            created_by=actor,
            expires_at=expires_at,
        )
        return created, raw_token, True

    def revoke(self, instance, *, actor=None):
        instance.revoke(actor=actor)
        return instance

    def resolve_public_campaign(self, raw_token):
        if not raw_token:
            raise PublicCampaignAccessError("invalid_token", "Campaign access link is invalid.", 404)

        token_hash = CampaignAccessToken.build_hash(raw_token)
        access_token = (
            self.repository.get_queryset()
            .filter(token_hash=token_hash)
            .first()
        )
        if not access_token:
            raise PublicCampaignAccessError("invalid_token", "Campaign access link is invalid.", 404)

        if access_token.is_revoked():
            raise PublicCampaignAccessError("revoked_token", "This campaign link has been revoked.", 410)

        if access_token.has_expired():
            raise PublicCampaignAccessError("expired_token", "This campaign link has expired.", 410)

        if access_token.has_campaign_ended():
            raise PublicCampaignAccessError(
                "campaign_ended",
                "This campaign link is no longer available because the campaign has ended.",
                410,
            )

        campaign = self.repository.get_public_campaign_queryset().filter(pk=access_token.campaign_id).first()
        if not campaign:
            raise PublicCampaignAccessError("invalid_token", "Campaign access link is invalid.", 404)

        access_token.mark_accessed()
        return access_token, campaign

    def get_effective_expiry(self, access_token):
        campaign_end = timezone.make_aware(datetime.combine(access_token.campaign.end_date, time.max))
        if access_token.expires_at:
            return min(access_token.expires_at, campaign_end)
        return campaign_end
