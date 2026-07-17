from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Case, CharField, Count, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.bookings.models import Booking
from apps.billing.models import Invoice, Payment
from apps.tenants.services import is_platform_super_admin, require_same_tenant, resolve_write_tenant, scope_queryset_to_tenant_path
from apps.poe.models import ProofOfExecution
from core.services import BaseService

from .models import Campaign, CampaignAccessToken
from .repositories import CampaignAccessTokenRepository, CampaignAssetRepository, CampaignRepository

SUMMARY_DECIMAL_FIELD = DecimalField(max_digits=14, decimal_places=2)
ZERO = Decimal("0.00")


def campaign_effective_status_query(status, *, today=None):
    today = today or timezone.localdate()
    normalized = str(status or "").lower()
    if normalized == Campaign.EffectiveStatus.CANCELLED:
        return Q(status=Campaign.Status.CANCELLED)
    if normalized == Campaign.EffectiveStatus.PAUSED:
        return Q(status=Campaign.Status.PAUSED)

    normal_lifecycle = ~Q(status__in=[Campaign.Status.CANCELLED, Campaign.Status.PAUSED])
    if normalized == Campaign.EffectiveStatus.UPCOMING:
        return normal_lifecycle & Q(start_date__gt=today)
    if normalized == Campaign.EffectiveStatus.ENDED:
        return normal_lifecycle & Q(end_date__lt=today)
    if normalized == Campaign.EffectiveStatus.ONGOING:
        return normal_lifecycle & Q(start_date__lte=today, end_date__gte=today)
    raise ValueError("Unsupported effective campaign status.")


def annotate_campaign_effective_status(queryset, *, today=None):
    today = today or timezone.localdate()
    return queryset.annotate(
        effective_lifecycle=Case(
            When(status=Campaign.Status.CANCELLED, then=Value(Campaign.EffectiveStatus.CANCELLED)),
            When(status=Campaign.Status.PAUSED, then=Value(Campaign.EffectiveStatus.PAUSED)),
            When(start_date__gt=today, then=Value(Campaign.EffectiveStatus.UPCOMING)),
            When(end_date__lt=today, then=Value(Campaign.EffectiveStatus.ENDED)),
            default=Value(Campaign.EffectiveStatus.ONGOING),
            output_field=CharField(),
        )
    )


def _can_view_campaign_billing(user=None) -> bool:
    return bool(
        user is None
        or is_platform_super_admin(user)
        or getattr(user, "role", None) in {"admin", "finance"}
    )


def _invoice_balance(invoice) -> Decimal:
    paid = invoice.payments.aggregate(total=Coalesce(Sum("amount"), ZERO, output_field=SUMMARY_DECIMAL_FIELD))["total"]
    total = invoice.grand_total or invoice.total_amount or ZERO
    return max(total - paid, ZERO)


def build_campaign_performance_analytics(*, user=None, queryset=None, today=None) -> dict:
    today = today or timezone.localdate()
    can_view_billing = _can_view_campaign_billing(user)
    queryset = queryset or scope_queryset_to_tenant_path(Campaign.objects.all(), user)
    campaigns = list(
        queryset.select_related("client").prefetch_related(
            "bookings__poe_records",
            "bookings__media_unit",
            "invoices__payments",
        )
    )
    ending_soon_cutoff = today + timedelta(days=7)
    rows = []
    risk_distribution = {"on_track": 0, "needs_attention": 0, "poe_risk": 0, "billing_risk": 0, "critical": 0}
    active_count = 0
    ending_soon_count = 0
    poe_risk_count = 0
    billing_risk_count = 0
    at_risk_count = 0

    for campaign in campaigns:
        bookings = [booking for booking in campaign.bookings.all() if booking.status != Booking.Status.CANCELLED]
        booked_sites = len({booking.media_unit_id for booking in bookings})
        approved_poe_sites = 0
        suspicious_poe_count = 0
        missing_poe_sites = 0
        for booking in bookings:
            if booking.poe_records.filter(verification_status=ProofOfExecution.VerificationStatus.VERIFIED).exists():
                approved_poe_sites += 1
            else:
                missing_poe_sites += 1
            suspicious_poe_count += booking.poe_records.filter(
                verification_status__in=[
                    ProofOfExecution.VerificationStatus.SUSPICIOUS,
                    ProofOfExecution.VerificationStatus.REJECTED,
                ]
            ).count()

        poe_completion = round((approved_poe_sites / booked_sites) * 100) if booked_sites else 0
        pending_poe_count = missing_poe_sites
        effective_status = campaign.effective_status_at(today)
        is_active = effective_status == Campaign.EffectiveStatus.ONGOING
        is_ending_soon = is_active and today <= campaign.end_date <= ending_soon_cutoff
        if is_active:
            active_count += 1
        if is_ending_soon:
            ending_soon_count += 1

        invoices = list(campaign.invoices.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]))
        total_invoiced = sum((invoice.grand_total or invoice.total_amount or ZERO for invoice in invoices), ZERO)
        total_collected = sum((payment.amount for invoice in invoices for payment in invoice.payments.all()), ZERO)
        pending_amount = max(total_invoiced - total_collected, ZERO)
        payment_completion = round((total_collected / total_invoiced) * Decimal("100")) if total_invoiced > ZERO else 0
        overdue_balance = ZERO
        overdue_invoice_count = 0
        for invoice in invoices:
            balance = _invoice_balance(invoice)
            if invoice.due_date and invoice.due_date < today and balance > ZERO:
                overdue_invoice_count += 1
                overdue_balance += balance

        has_poe_risk = (booked_sites > 0 and missing_poe_sites > 0 and is_active) or suspicious_poe_count > 0
        has_billing_risk = can_view_billing and overdue_balance > ZERO
        if has_poe_risk:
            poe_risk_count += 1
        if has_billing_risk:
            billing_risk_count += 1

        if has_billing_risk and (suspicious_poe_count > 0 or is_ending_soon):
            risk = "critical"
        elif suspicious_poe_count > 0 and is_ending_soon:
            risk = "critical"
        elif has_billing_risk:
            risk = "billing_risk"
        elif has_poe_risk:
            risk = "poe_risk"
        elif is_ending_soon and pending_amount > ZERO and can_view_billing:
            risk = "needs_attention"
        elif is_ending_soon and booked_sites > approved_poe_sites:
            risk = "needs_attention"
        else:
            risk = "on_track"

        risk_distribution[risk] += 1
        if risk != "on_track":
            at_risk_count += 1

        billing_status = "hidden"
        payment_collection_status = "hidden"
        if can_view_billing:
            if not invoices:
                billing_status = "no_invoice"
            elif overdue_balance > ZERO:
                billing_status = "overdue"
            elif pending_amount <= ZERO and total_invoiced > ZERO:
                billing_status = "collected"
            elif total_collected > ZERO:
                billing_status = "partially_collected"
            else:
                billing_status = "pending_collection"
            payment_collection_status = billing_status

        rows.append(
            {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "campaign_code": campaign.code,
                "status": campaign.status,
                "effective_status": effective_status,
                "start_date": campaign.start_date,
                "end_date": campaign.end_date,
                "is_active": is_active,
                "is_ending_soon": is_ending_soon,
                "booked_sites_count": booked_sites,
                "sites_with_approved_poe": approved_poe_sites,
                "sites_missing_poe": missing_poe_sites,
                "pending_poe_count": pending_poe_count,
                "poe_completion_percentage": poe_completion,
                "suspicious_poe_count": suspicious_poe_count,
                "invoice_generated": bool(invoices),
                "billing_status": billing_status,
                "payment_collection_status": payment_collection_status,
                "payment_completion_percentage": payment_completion if can_view_billing else 0,
                "has_overdue_invoice": overdue_balance > ZERO if can_view_billing else False,
                "operational_delay_indicators": [
                    label
                    for label, active in [
                        ("ending_soon", is_ending_soon),
                        ("missing_poe", pending_poe_count > 0),
                        ("suspicious_poe", suspicious_poe_count > 0),
                        ("overdue_billing", overdue_balance > ZERO and can_view_billing),
                    ]
                    if active
                ],
                "pending_amount": pending_amount if can_view_billing else ZERO,
                "overdue_amount": overdue_balance if can_view_billing else ZERO,
                "risk_status": risk,
            }
        )

    return {
        "active_campaigns": active_count,
        "ending_soon_count": ending_soon_count,
        "poe_risk_count": poe_risk_count,
        "billing_risk_count": billing_risk_count,
        "at_risk_count": at_risk_count,
        "critical_count": risk_distribution["critical"],
        "risk_distribution": [{"risk": key, "total": value} for key, value in risk_distribution.items()],
        "poe_completion_trend": [
            {
                "campaign": row["campaign_code"],
                "completion": row["poe_completion_percentage"],
                "missing": row["sites_missing_poe"],
            }
            for row in sorted(rows, key=lambda row: row["end_date"])[:10]
        ],
        "operational_health_trend": [
            {
                "campaign": row["campaign_code"],
                "risk": row["risk_status"],
                "indicators": len(row["operational_delay_indicators"]),
            }
            for row in sorted(rows, key=lambda row: (row["risk_status"] == "on_track", row["end_date"]))[:10]
        ],
        "campaigns": sorted(rows, key=lambda row: (row["risk_status"] == "on_track", row["end_date"], row["campaign_id"]))[:12],
        "can_view_billing": can_view_billing,
    }


class CampaignService(BaseService):
    repository_class = CampaignRepository

    def get_active_campaigns(self):
        return self.get_queryset().filter(campaign_effective_status_query(Campaign.EffectiveStatus.ONGOING))

    def get_summary(self, user=None):
        cache_key = f"dashboard:campaigns:{self._dashboard_cache_version()}:{getattr(user, 'id', 'anon')}:{getattr(user, 'role', '')}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        queryset = self.get_queryset(user=user)
        today = timezone.localdate()
        ongoing_filter = campaign_effective_status_query(Campaign.EffectiveStatus.ONGOING, today=today)
        summary = queryset.aggregate(
            total_campaigns=Count("id"),
            active_campaigns=Count("id", filter=ongoing_filter),
            draft_campaigns=Count("id", filter=Q(status=Campaign.Status.DRAFT)),
            completed_campaigns=Count("id", filter=Q(status=Campaign.Status.COMPLETED)),
            total_budget=Coalesce(Sum("budget"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD),
            active_budget=Coalesce(
                Sum("budget", filter=ongoing_filter),
                Decimal("0.00"),
                output_field=SUMMARY_DECIMAL_FIELD,
            ),
            total_bookings=Count("bookings", distinct=True),
            live_bookings=Count("bookings", filter=Q(bookings__status=Booking.Status.LIVE), distinct=True),
            approved_assets=Count("assets", filter=Q(assets__is_approved=True), distinct=True),
        )
        performance = build_campaign_performance_analytics(user=user, queryset=queryset)
        summary["ending_soon_count"] = performance["ending_soon_count"]
        summary["campaigns_at_risk"] = performance["at_risk_count"]
        summary["campaigns_poe_risk"] = performance["poe_risk_count"]
        summary["campaigns_billing_risk"] = performance["billing_risk_count"]
        summary["critical_campaigns"] = performance["critical_count"]
        cache.set(cache_key, summary, getattr(settings, "OMMS_DASHBOARD_CACHE_SECONDS", 60))
        return summary

    def create(self, actor=None, **validated_data):
        if actor and "tenant" not in validated_data:
            validated_data["tenant"] = resolve_write_tenant(actor)
        elif actor:
            validated_data["tenant"] = resolve_write_tenant(actor, validated_data.get("tenant"))
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

    def create(self, actor=None, **validated_data):
        if actor:
            require_same_tenant(actor, validated_data["campaign"].tenant, message="You can only add assets to your own company campaigns.")
        return super().create(actor=actor, **validated_data)


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
