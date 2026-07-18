from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Prefetch, Q
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.billing.models import CampaignEstimate, CampaignEstimateLine
from apps.billing.services import CampaignEstimateLineService, CampaignEstimateService
from apps.bookings.models import Booking
from apps.bookings.services import BookingService
from apps.campaigns.models import Campaign
from apps.campaigns.services import CampaignService
from apps.inventory.models import MediaUnit, RateCard
from apps.observability.services import record_audit_event
from apps.tenants.models import Tenant
from apps.tenants.services import get_user_tenant, is_platform_super_admin, require_same_tenant
from apps.users.models import User

from .models import CampaignProposal, CampaignProposalLine, MediaPlannerShareLink


ACTIVE_BOOKING_STATUSES = (Booking.Status.PENDING, Booking.Status.CONFIRMED, Booking.Status.LIVE)


class PlannerAccessError(Exception):
    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AvailabilityStatus:
    AVAILABLE = "available"
    PARTIALLY_AVAILABLE = "partially_available"
    BOOKED = "booked"
    ON_HOLD = "on_hold"
    UNDER_MAINTENANCE = "under_maintenance"
    UNAVAILABLE = "unavailable"


class InventoryAvailabilityService:
    def validate_dates(self, start_date: date | None, end_date: date | None):
        if bool(start_date) != bool(end_date):
            raise ValidationError({"dates": ["Select both campaign start and end dates."]})
        if start_date and end_date and end_date < start_date:
            raise ValidationError({"end_date": ["End date must be on or after start date."]})

    def booking_prefetch(self, start_date=None, end_date=None):
        queryset = Booking.objects.filter(status__in=ACTIVE_BOOKING_STATUSES).order_by("start_date", "id")
        if start_date and end_date:
            queryset = queryset.filter(start_date__lte=end_date, end_date__gte=start_date)
        return Prefetch("bookings", queryset=queryset, to_attr="planner_bookings")

    def resolve(self, unit, *, start_date=None, end_date=None, exclude_booking_id=None, require_publication=True):
        self.validate_dates(start_date, end_date)
        if require_publication and not unit.is_publicly_listed:
            return self._result(AvailabilityStatus.UNAVAILABLE, "Not published for client planning.")
        if unit.status == MediaUnit.Status.MAINTENANCE:
            return self._result(AvailabilityStatus.UNDER_MAINTENANCE, "Temporarily under maintenance.")
        if unit.status == MediaUnit.Status.RETIRED:
            return self._result(AvailabilityStatus.UNAVAILABLE, "Not operationally available.")
        if unit.status == MediaUnit.Status.RESERVED:
            return self._result(AvailabilityStatus.ON_HOLD, "Currently on operational hold.")
        if unit.status != MediaUnit.Status.AVAILABLE:
            return self._result(AvailabilityStatus.UNAVAILABLE, "Not operationally available.")
        if not start_date or not end_date:
            return self._result(AvailabilityStatus.AVAILABLE, "Select dates for live availability.")

        prefetched = getattr(unit, "planner_bookings", None)
        bookings = prefetched if prefetched is not None else list(
            unit.bookings.filter(
                status__in=ACTIVE_BOOKING_STATUSES,
                start_date__lte=end_date,
                end_date__gte=start_date,
            ).order_by("start_date", "id")
        )
        if exclude_booking_id:
            bookings = [booking for booking in bookings if booking.id != exclude_booking_id]
        if not bookings:
            return self._result(AvailabilityStatus.AVAILABLE, "Available for the selected dates.")

        confirmed = [booking for booking in bookings if booking.status in {Booking.Status.CONFIRMED, Booking.Status.LIVE}]
        pending = [booking for booking in bookings if booking.status == Booking.Status.PENDING]
        blocking = confirmed or pending
        fully_covered = any(booking.start_date <= start_date and booking.end_date >= end_date for booking in blocking)
        if confirmed and fully_covered:
            return self._result(AvailabilityStatus.BOOKED, "Booked for the selected dates.", bookings)
        if pending and fully_covered and not confirmed:
            return self._result(AvailabilityStatus.ON_HOLD, "A provisional booking is being reviewed.", bookings)
        return self._result(
            AvailabilityStatus.PARTIALLY_AVAILABLE,
            "Only part of the selected date range is currently available.",
            bookings,
        )

    def assert_bookable(self, unit, *, start_date, end_date, exclude_booking_id=None):
        result = self.resolve(
            unit,
            start_date=start_date,
            end_date=end_date,
            exclude_booking_id=exclude_booking_id,
            require_publication=False,
        )
        if result["status"] != AvailabilityStatus.AVAILABLE:
            raise ValidationError(f"The selected media unit is {result['label'].lower()} for the given date range.")
        return result

    def _result(self, status, reason, bookings=None):
        labels = {
            AvailabilityStatus.AVAILABLE: "Available",
            AvailabilityStatus.PARTIALLY_AVAILABLE: "Partially available",
            AvailabilityStatus.BOOKED: "Booked",
            AvailabilityStatus.ON_HOLD: "On hold",
            AvailabilityStatus.UNDER_MAINTENANCE: "Under maintenance",
            AvailabilityStatus.UNAVAILABLE: "Unavailable",
        }
        return {
            "status": status,
            "label": labels[status],
            "reason": reason,
            "conflict_count": len(bookings or []),
        }


def resolve_planner_link(raw_token, *, mark_access=False):
    if not raw_token:
        raise PlannerAccessError("invalid_token", "This media planner link is invalid.", 404)
    link = (
        MediaPlannerShareLink.objects.select_related("tenant", "client", "created_by")
        .filter(token_hash=MediaPlannerShareLink.build_hash(raw_token))
        .first()
    )
    if not link:
        raise PlannerAccessError("invalid_token", "This media planner link is invalid.", 404)
    if link.is_revoked:
        raise PlannerAccessError("revoked_link", "This media planner link has been revoked.", 410)
    if link.is_expired:
        raise PlannerAccessError("expired_link", "This media planner link has expired.", 410)
    if link.tenant.status not in {link.tenant.Status.ACTIVE, link.tenant.Status.TRIAL}:
        raise PlannerAccessError("tenant_unavailable", "This media planner is temporarily unavailable.", 410)
    if mark_access:
        now = timezone.now()
        should_audit = not link.last_accessed_at or (now - link.last_accessed_at).total_seconds() >= 1800
        link.last_accessed_at = now
        link.save(update_fields=["last_accessed_at", "updated_at"])
        if should_audit:
            _audit(
                "planner.link.opened",
                link,
                "A client opened a Live Media Planner link.",
                metadata={"tenant_id": link.tenant_id},
            )
    return link


def _coerced_allowed_values(values):
    if values is None or values == "":
        return []
    elif isinstance(values, str):
        raw_values = values.split(",")
    elif isinstance(values, (list, tuple, set)):
        raw_values = []
        for value in values:
            if isinstance(value, str) and "," in value:
                raw_values.extend(value.split(","))
            else:
                raw_values.append(value)
    else:
        raw_values = [values]
    return [str(value).strip() for value in raw_values if str(value).strip()]


def _normalized_allowed_values(values):
    normalized = []
    seen = set()

    for text in _coerced_allowed_values(values):
        key = text.casefold()
        if text and key not in seen:
            normalized.append(key)
            seen.add(key)
    return normalized


def _filter_normalized_text(queryset, field_name, values, alias):
    normalized = _normalized_allowed_values(values)
    if not normalized:
        return queryset
    return queryset.annotate(**{alias: Lower(Trim(F(field_name)))}).filter(**{f"{alias}__in": normalized})


def planner_unit_queryset(link, *, start_date=None, end_date=None):
    queryset = (
        MediaUnit.objects.select_related("site")
        .prefetch_related("images", "site__images", InventoryAvailabilityService().booking_prefetch(start_date, end_date))
        .filter(site__tenant=link.tenant, is_publicly_listed=True)
        .exclude(status=MediaUnit.Status.RETIRED)
    )
    if link.allowed_cities:
        queryset = _filter_normalized_text(queryset, "site__city", link.allowed_cities, "_planner_city")
    if link.allowed_regions:
        queryset = _filter_normalized_text(queryset, "site__state", link.allowed_regions, "_planner_region")
    if link.allowed_inventory_types:
        inventory_types = _coerced_allowed_values(link.allowed_inventory_types)
        queryset = queryset.filter(Q(site_type__in=inventory_types) | Q(site__site_type__in=inventory_types))
    return queryset.order_by("site__city", "site__name", "unit_code", "id")


def planner_inventory_diagnostics(link, *, start_date=None, end_date=None):
    availability_service = InventoryAvailabilityService()
    tenant_units = MediaUnit.objects.select_related("site").filter(site__tenant=link.tenant)
    public_units = tenant_units.filter(is_publicly_listed=True)
    operational_units = public_units.exclude(status=MediaUnit.Status.RETIRED)
    allowed_city_units = operational_units
    if link.allowed_cities:
        allowed_city_units = _filter_normalized_text(allowed_city_units, "site__city", link.allowed_cities, "_diagnostic_city")
    eligible_queryset = planner_unit_queryset(link, start_date=start_date, end_date=end_date)
    eligible_units = list(eligible_queryset)
    date_available_count = sum(
        1
        for unit in eligible_units
        if availability_service.resolve(unit, start_date=start_date, end_date=end_date)["status"] == AvailabilityStatus.AVAILABLE
    )
    excluded = {
        "not_published": tenant_units.filter(is_publicly_listed=False).count(),
        "city_not_allowed": 0,
        "inactive": public_units.filter(status__in=[MediaUnit.Status.RETIRED, MediaUnit.Status.MAINTENANCE]).count(),
        "unavailable_for_dates": max(len(eligible_units) - date_available_count, 0) if start_date and end_date else 0,
        "missing_public_information": 0,
    }

    allowed_city_values = _normalized_allowed_values(link.allowed_cities)
    if allowed_city_values:
        excluded["city_not_allowed"] = (
            operational_units.annotate(_planner_city=Lower(Trim(F("site__city"))))
            .exclude(_planner_city__in=allowed_city_values)
            .count()
        )

    return {
        "counts": {
            "base_media_units": MediaUnit.objects.count(),
            "tenant_scoped": tenant_units.count(),
            "publicly_listed": public_units.count(),
            "operational": operational_units.count(),
            "allowed_city": allowed_city_units.count(),
            "date_available": date_available_count,
            "eligible": eligible_queryset.count(),
        },
        "excluded": excluded,
        "allowed_cities": _normalized_allowed_values(link.allowed_cities),
    }


def create_planner_link(*, actor, **values):
    requested_tenant = values.pop("tenant", None)
    if is_platform_super_admin(actor):
        tenant = requested_tenant
        if not tenant:
            raise ValidationError({"tenant": ["Select a client company for this planner link."]})
        if tenant.tenant_type != Tenant.TenantType.CLIENT:
            raise ValidationError({"tenant": ["Select a client company, not the platform tenant."]})
    else:
        tenant = get_user_tenant(actor)
        if not tenant:
            raise ValidationError({"tenant": ["Select a client company."]})
        if requested_tenant is not None:
            require_same_tenant(actor, requested_tenant, message="You can only create planner links for your own company.")
    client = values.get("client")
    if client and client.tenant_id != tenant.id:
        raise ValidationError({"client": ["Client must belong to the selected company."]})
    if values.get("pricing_mode") == MediaPlannerShareLink.PricingMode.CLIENT_RATE_CARD:
        values["show_rates"] = False
    link, raw_token = MediaPlannerShareLink.create_with_token(tenant=tenant, created_by=actor, **values)
    _audit(
        "planner.link.generated",
        link,
        "A Live Media Planner link was generated.",
        actor=actor,
        metadata={"tenant_id": tenant.id, "pricing_mode": link.pricing_mode},
    )
    return link, raw_token


def revoke_planner_link(*, actor, link):
    if not is_platform_super_admin(actor):
        require_same_tenant(actor, link.tenant, message="You can only revoke your own company planner links.")
    if not link.revoked_at:
        link.revoked_at = timezone.now()
        link.save(update_fields=["revoked_at", "updated_at"])
        _audit(
            "planner.link.revoked",
            link,
            "A Live Media Planner link was revoked.",
            actor=actor,
            metadata={"tenant_id": link.tenant_id},
        )
    return link


def submit_proposal(*, link, validated_data):
    if not link.allow_proposal_submission:
        raise ValidationError({"detail": ["Proposal submission is disabled for this planner link."]})
    start_date = validated_data["requested_start_date"]
    end_date = validated_data["requested_end_date"]
    availability_service = InventoryAvailabilityService()
    availability_service.validate_dates(start_date, end_date)
    unit_public_ids = list(dict.fromkeys(validated_data.pop("unit_public_ids")))
    if not unit_public_ids:
        raise ValidationError({"unit_public_ids": ["Select at least one advertising unit."]})
    idempotency_key = validated_data.pop("idempotency_key", "")
    if idempotency_key:
        existing = CampaignProposal.objects.filter(share_link=link, idempotency_key=idempotency_key).first()
        if existing:
            return existing, False

    units = list(planner_unit_queryset(link, start_date=start_date, end_date=end_date).filter(public_id__in=unit_public_ids))
    if len(units) != len(unit_public_ids):
        raise ValidationError({"unit_public_ids": ["One or more selected units are unavailable through this planner link."]})

    line_payloads = []
    preliminary_subtotal = Decimal("0.00")
    conflict_count = 0
    for unit in units:
        availability = availability_service.resolve(unit, start_date=start_date, end_date=end_date)
        # Preserve the authoritative selling-rate snapshot internally even when
        # the client-facing planner intentionally hides pricing.
        rate = unit.monthly_rate
        tax_rate = _resolve_tax_rate(unit, start_date, end_date)
        if link.effective_show_rates:
            preliminary_subtotal += rate
        if availability["status"] != AvailabilityStatus.AVAILABLE:
            conflict_count += 1
        line_payloads.append((unit, rate, tax_rate, availability))

    with transaction.atomic():
        proposal = CampaignProposal.objects.create(
            tenant=link.tenant,
            share_link=link,
            client=link.client,
            preliminary_subtotal=preliminary_subtotal,
            selected_unit_count=len(line_payloads),
            availability_conflict_count=conflict_count,
            idempotency_key=idempotency_key,
            **validated_data,
        )
        for unit, rate, tax_rate, availability in line_payloads:
            CampaignProposalLine.objects.create(
                proposal=proposal,
                media_unit=unit,
                unit_public_id=unit.public_id,
                unit_code=unit.unit_code,
                location_name=unit.site.name,
                public_address=unit.site.address,
                city=unit.site.city,
                region=unit.site.state,
                width=unit.width,
                height=unit.height,
                facing_direction=unit.facing_direction,
                display_format=unit.site_type,
                is_illuminated=unit.is_illuminated,
                monthly_rate_snapshot=rate,
                tax_rate_snapshot=tax_rate,
                availability_status=availability["status"],
                availability_snapshot=availability,
            )
        _audit(
            "planner.proposal.submitted",
            proposal,
            "A client submitted a campaign proposal from Live Media Planner.",
            metadata={
                "tenant_id": proposal.tenant_id,
                "selected_units": proposal.selected_unit_count,
                "conflicts": proposal.availability_conflict_count,
            },
        )
    return proposal, True


def recheck_proposal_availability(*, proposal, actor=None):
    service = InventoryAvailabilityService()
    conflict_count = 0
    with transaction.atomic():
        for line in proposal.lines.select_related("media_unit", "media_unit__site"):
            if not line.media_unit or line.media_unit.site.tenant_id != proposal.tenant_id:
                availability = service._result(AvailabilityStatus.UNAVAILABLE, "The original unit is no longer available.")
            else:
                availability = service.resolve(
                    line.media_unit,
                    start_date=proposal.requested_start_date,
                    end_date=proposal.requested_end_date,
                )
            line.availability_status = availability["status"]
            line.availability_snapshot = availability
            line.save(update_fields=["availability_status", "availability_snapshot", "updated_at"])
            if availability["status"] != AvailabilityStatus.AVAILABLE:
                conflict_count += 1
        proposal.availability_conflict_count = conflict_count
        if conflict_count == 0 and proposal.status in {CampaignProposal.Status.SUBMITTED, CampaignProposal.Status.UNDER_REVIEW}:
            proposal.status = CampaignProposal.Status.AVAILABILITY_CONFIRMED
        proposal.reviewed_by = actor or proposal.reviewed_by
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=["availability_conflict_count", "status", "reviewed_by", "reviewed_at", "updated_at"])
    return proposal


def create_estimate_from_proposal(*, proposal, actor, client=None):
    if proposal.estimate_id:
        return proposal.estimate, False
    client = client or proposal.client
    if not client or client.role != User.Role.CLIENT:
        raise ValidationError({"client": ["Assign a tenant client before preparing an estimate."]})
    require_same_tenant(actor, proposal.tenant, message="You can only prepare estimates for your own company proposals.")
    if client.tenant_id != proposal.tenant_id:
        raise ValidationError({"client": ["Client must belong to the proposal company."]})

    with transaction.atomic():
        estimate = CampaignEstimateService().create(
            actor=actor,
            client=client,
            title=proposal.campaign_name,
            start_date=proposal.requested_start_date,
            end_date=proposal.requested_end_date,
            status=CampaignEstimate.Status.DRAFT,
            notes=f"Prepared from Live Media Planner proposal {proposal.reference}.\n{proposal.notes}".strip(),
        )
        for line in proposal.lines.select_related("media_unit"):
            CampaignEstimateLineService().create(
                actor=actor,
                estimate=estimate,
                media_unit=line.media_unit,
                description=f"{line.unit_code} · {line.location_name}",
                start_date=proposal.requested_start_date,
                end_date=proposal.requested_end_date,
                quantity=Decimal("1.00"),
                unit_rate=line.monthly_rate_snapshot or Decimal("0.00"),
                tax_rate=line.tax_rate_snapshot,
            )
        proposal.client = client
        proposal.estimate = estimate
        proposal.status = CampaignProposal.Status.ESTIMATE_PREPARED
        proposal.reviewed_by = actor
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=["client", "estimate", "status", "reviewed_by", "reviewed_at", "updated_at"])
        _audit(
            "planner.proposal.estimate_created",
            proposal,
            "A draft estimate was created from a client proposal.",
            actor=actor,
            metadata={"tenant_id": proposal.tenant_id, "estimate_id": estimate.id},
        )
    return estimate, True


def convert_proposal_to_campaign(*, proposal, actor, campaign_code):
    if proposal.converted_campaign_id:
        return proposal.converted_campaign, False
    if proposal.status != CampaignProposal.Status.CLIENT_APPROVED:
        raise ValidationError({"status": ["Only a client-approved proposal can be converted."]})
    if not proposal.client:
        raise ValidationError({"client": ["Assign a tenant client before conversion."]})
    if proposal.estimate and proposal.estimate.status != CampaignEstimate.Status.APPROVED:
        raise ValidationError({"estimate": ["The linked estimate must be client approved before conversion."]})
    require_same_tenant(actor, proposal.tenant, message="You can only convert your own company proposals.")
    proposal = recheck_proposal_availability(proposal=proposal, actor=actor)
    if proposal.availability_conflict_count:
        raise ValidationError({"availability": ["Resolve inventory conflicts before campaign conversion."]})

    with transaction.atomic():
        campaign = CampaignService().create(
            actor=actor,
            tenant=proposal.tenant,
            client=proposal.client,
            account_manager=proposal.assigned_to or actor,
            name=proposal.campaign_name,
            code=campaign_code,
            start_date=proposal.requested_start_date,
            end_date=proposal.requested_end_date,
            budget=proposal.estimate.total_amount if proposal.estimate else proposal.preliminary_subtotal,
            status=Campaign.Status.DRAFT,
            objective=proposal.objective,
        )
        for line in proposal.lines.select_related("media_unit"):
            if not line.media_unit:
                raise ValidationError({"availability": [f"Unit {line.unit_code} is no longer available."]})
            BookingService().create(
                actor=actor,
                campaign=campaign,
                media_unit=line.media_unit,
                start_date=proposal.requested_start_date,
                end_date=proposal.requested_end_date,
                booked_rate=line.monthly_rate_snapshot or line.media_unit.monthly_rate,
                status=Booking.Status.PENDING,
                remarks=f"Created from proposal {proposal.reference}; requires internal confirmation.",
            )
        proposal.converted_campaign = campaign
        proposal.status = CampaignProposal.Status.CONVERTED_TO_CAMPAIGN
        proposal.save(update_fields=["converted_campaign", "status", "updated_at"])
        if proposal.estimate and not proposal.estimate.campaign_id:
            proposal.estimate.campaign = campaign
            proposal.estimate.save(update_fields=["campaign", "updated_at"])
        _audit(
            "planner.proposal.converted",
            proposal,
            "A client-approved proposal was converted to a draft campaign and pending bookings.",
            actor=actor,
            metadata={"tenant_id": proposal.tenant_id, "campaign_id": campaign.id},
        )
    return campaign, True


def _resolve_tax_rate(unit, start_date, end_date):
    rate_card = (
        RateCard.objects.filter(unit=unit, start_date__lte=start_date, end_date__gte=end_date)
        .order_by("-start_date", "-id")
        .first()
    )
    return rate_card.tax_percentage if rate_card else Decimal("0.00")


def _audit(event_type, entity, summary, *, actor=None, metadata=None):
    return record_audit_event(
        event_type=event_type,
        entity_type=entity._meta.model_name,
        entity_id=entity.id,
        actor=actor,
        summary=summary,
        metadata=metadata or {},
        client_reference=getattr(entity, "reference", ""),
    )
