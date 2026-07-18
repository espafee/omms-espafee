from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.observability.services import record_audit_event
from apps.tenants.services import get_user_tenant, is_platform_super_admin
from core.pagination import DefaultPageNumberPagination
from core.permissions import RoleBasedPermission
from core.roles import ADMIN, FINANCE, OPERATIONS, SALES

from .models import CampaignProposal, MediaPlannerShareLink
from .serializers import (
    CampaignProposalSerializer,
    MediaPlannerShareLinkSerializer,
    ProposalAssignmentSerializer,
    ProposalConversionSerializer,
    ProposalEstimateSerializer,
    ProposalStatusSerializer,
    PublicProposalSubmitSerializer,
    serialize_public_unit,
)
from .services import (
    AvailabilityStatus,
    InventoryAvailabilityService,
    PlannerAccessError,
    convert_proposal_to_campaign,
    create_estimate_from_proposal,
    create_planner_link,
    planner_unit_queryset,
    recheck_proposal_availability,
    resolve_planner_link,
    revoke_planner_link,
    submit_proposal,
)


INTERNAL_PLANNER_ROLES = (ADMIN, SALES, OPERATIONS, FINANCE)


class MediaPlannerShareLinkViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MediaPlannerShareLinkSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = INTERNAL_PLANNER_ROLES
    write_roles = (ADMIN, SALES)
    filterset_fields = ["tenant", "client", "pricing_mode"]
    search_fields = ["title", "client__email", "client__organization_name", "token_prefix"]
    ordering_fields = ["created_at", "expires_at", "last_accessed_at"]

    def get_queryset(self):
        queryset = MediaPlannerShareLink.objects.select_related("tenant", "client", "created_by")
        if not is_platform_super_admin(self.request.user):
            queryset = queryset.filter(tenant=get_user_tenant(self.request.user))
        return queryset.order_by("-created_at", "-id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link, raw_token = create_planner_link(actor=request.user, **serializer.validated_data)
        payload = MediaPlannerShareLinkSerializer(link, context=self.get_serializer_context()).data
        payload["public_path"] = f"/media-planner/{raw_token}"
        payload["token"] = raw_token
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        link = revoke_planner_link(actor=request.user, link=self.get_object())
        return Response(self.get_serializer(link).data)


class CampaignProposalViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CampaignProposalSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = INTERNAL_PLANNER_ROLES
    filterset_fields = ["status", "client", "assigned_to", "availability_conflict_count"]
    search_fields = ["reference", "campaign_name", "brand_company", "contact_name", "contact_email"]
    ordering_fields = ["submitted_at", "preliminary_subtotal", "selected_unit_count", "availability_conflict_count"]

    def get_queryset(self):
        queryset = CampaignProposal.objects.select_related(
            "tenant", "share_link", "client", "reviewed_by", "assigned_to", "estimate", "converted_campaign"
        ).prefetch_related("lines__media_unit__site", "lines__media_unit__bookings")
        if not is_platform_super_admin(self.request.user):
            queryset = queryset.filter(tenant=get_user_tenant(self.request.user))
        submitted_from = self.request.query_params.get("submitted_from")
        submitted_to = self.request.query_params.get("submitted_to")
        conflict_state = self.request.query_params.get("conflict_state")
        if submitted_from:
            queryset = queryset.filter(submitted_at__date__gte=submitted_from)
        if submitted_to:
            queryset = queryset.filter(submitted_at__date__lte=submitted_to)
        if conflict_state == "with_conflicts":
            queryset = queryset.filter(availability_conflict_count__gt=0)
        elif conflict_state == "clear":
            queryset = queryset.filter(availability_conflict_count=0)
        return queryset.order_by("-submitted_at", "-id")

    def _assert_tenant(self, proposal):
        if not is_platform_super_admin(self.request.user) and proposal.tenant_id != getattr(self.request.user, "tenant_id", None):
            raise PermissionDenied("You can only manage proposals for your own company.")

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        proposal = self.get_object()
        serializer = ProposalStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        previous = proposal.status
        proposal.status = serializer.validated_data["status"]
        proposal.reviewed_by = request.user
        proposal.reviewed_at = timezone.now()
        proposal.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        record_audit_event(
            event_type="planner.proposal.status_changed",
            entity_type="campaignproposal",
            entity_id=proposal.id,
            actor=request.user,
            summary="A client proposal status was changed.",
            metadata={"tenant_id": proposal.tenant_id, "from_status": previous, "to_status": proposal.status},
            client_reference=proposal.reference,
        )
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        proposal = self.get_object()
        serializer = ProposalAssignmentSerializer(data=request.data, context={"proposal": proposal})
        serializer.is_valid(raise_exception=True)
        proposal.assigned_to = serializer.validated_data["assigned_to"]
        proposal.save(update_fields=["assigned_to", "updated_at"])
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=["post"], url_path="recheck-availability")
    def recheck_availability(self, request, pk=None):
        proposal = recheck_proposal_availability(proposal=self.get_object(), actor=request.user)
        return Response(self.get_serializer(proposal).data)

    @action(detail=True, methods=["post"], url_path="create-estimate")
    def create_estimate(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in {ADMIN, FINANCE}):
            raise PermissionDenied("Only company administrators or finance users can prepare estimates.")
        proposal = self.get_object()
        serializer = ProposalEstimateSerializer(data=request.data, context={"proposal": proposal})
        serializer.is_valid(raise_exception=True)
        estimate, created = create_estimate_from_proposal(
            proposal=proposal,
            actor=request.user,
            client=serializer.validated_data.get("client"),
        )
        proposal.refresh_from_db()
        return Response(
            {"created": created, "estimate_id": estimate.id, "estimate_number": estimate.estimate_number, "proposal": self.get_serializer(proposal).data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="convert-to-campaign")
    def convert_to_campaign(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in {ADMIN, SALES}):
            raise PermissionDenied("Only administrators or sales users can convert approved proposals.")
        proposal = self.get_object()
        serializer = ProposalConversionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        campaign, created = convert_proposal_to_campaign(
            proposal=proposal,
            actor=request.user,
            campaign_code=serializer.validated_data["campaign_code"],
        )
        return Response(
            {"created": created, "campaign_id": campaign.id, "campaign_code": campaign.code},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PublicMediaPlannerView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "public_media_planner"

    def get(self, request, token):
        try:
            link = resolve_planner_link(token, mark_access=True)
        except PlannerAccessError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=exc.status_code)

        start_date = _parse_date(request.query_params.get("start_date"))
        end_date = _parse_date(request.query_params.get("end_date"))
        try:
            InventoryAvailabilityService().validate_dates(start_date, end_date)
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        queryset = planner_unit_queryset(link, start_date=start_date, end_date=end_date)
        queryset = _filter_public_units(queryset, request, link)
        paginator = DefaultPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        units = page if page is not None else list(queryset)
        availability_service = InventoryAvailabilityService()
        results = [
            serialize_public_unit(
                unit,
                link=link,
                request=request,
                availability=availability_service.resolve(unit, start_date=start_date, end_date=end_date),
            )
            for unit in units
        ]
        context = {
            "planner": {
                "title": link.title,
                "tenant_name": link.tenant.name,
                "client_name": link.client.organization_name or link.client.get_full_name() or link.client.email if link.client else "",
                "contact_email": link.tenant.contact_email,
                "expires_at": link.expires_at,
                "show_rates": link.effective_show_rates,
                "pricing_mode": link.pricing_mode,
                "allow_proposal_submission": link.allow_proposal_submission,
                "allow_image_download": link.allow_image_download,
                "client_rate_card_available": False,
            },
            "filters": {
                "cities": list(queryset.order_by().values_list("site__city", flat=True).distinct()[:100]),
                "locations": list(queryset.order_by().values_list("site__name", flat=True).distinct()[:100]),
            },
            "results": results,
        }
        if page is not None:
            response = paginator.get_paginated_response(results)
            response.data.update({key: value for key, value in context.items() if key != "results"})
            return response
        return Response(context)


class PublicMediaProposalSubmitView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "public_media_proposal"

    def post(self, request, token):
        try:
            link = resolve_planner_link(token)
        except PlannerAccessError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=exc.status_code)
        serializer = PublicProposalSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposal, created = submit_proposal(link=link, validated_data=dict(serializer.validated_data))
        return Response(
            {
                "reference": proposal.reference,
                "status": proposal.status,
                "selected_unit_count": proposal.selected_unit_count,
                "availability_conflict_count": proposal.availability_conflict_count,
                "created": created,
                "message": "Proposal submitted for formal review. No inventory has been booked yet.",
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def _parse_date(value):
    if not value:
        return None
    from django.utils.dateparse import parse_date

    parsed = parse_date(value)
    if not parsed:
        raise ValidationError({"dates": ["Use ISO date format YYYY-MM-DD."]})
    return parsed


def _filter_public_units(queryset, request, link):
    params = request.query_params
    search = params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(unit_code__icontains=search)
            | Q(site__name__icontains=search)
            | Q(site__address__icontains=search)
            | Q(site__city__icontains=search)
        )
    if params.get("city"):
        queryset = queryset.filter(site__city=params["city"])
    if params.get("location"):
        queryset = queryset.filter(site__name=params["location"])
    if params.get("display_format"):
        queryset = queryset.filter(site_type=params["display_format"])
    if params.get("facing"):
        queryset = queryset.filter(facing_direction__iexact=params["facing"])
    if params.get("illumination") in {"true", "false"}:
        queryset = queryset.filter(is_illuminated=params["illumination"] == "true")
    if params.get("width"):
        queryset = queryset.filter(width=params["width"])
    if params.get("height"):
        queryset = queryset.filter(height=params["height"])
    if link.effective_show_rates:
        if params.get("min_price"):
            queryset = queryset.filter(monthly_rate__gte=params["min_price"])
        if params.get("max_price"):
            queryset = queryset.filter(monthly_rate__lte=params["max_price"])
    availability = params.get("availability")
    if availability and availability == AvailabilityStatus.AVAILABLE:
        start_date = _parse_date(params.get("start_date"))
        end_date = _parse_date(params.get("end_date"))
        if start_date and end_date:
            blocked_ids = [
                unit.id
                for unit in queryset
                if InventoryAvailabilityService().resolve(unit, start_date=start_date, end_date=end_date)["status"]
                != AvailabilityStatus.AVAILABLE
            ]
            queryset = queryset.exclude(id__in=blocked_ids)
    return queryset.order_by("site__city", "site__name", "unit_code", "id")
