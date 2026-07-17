from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.serializers import CampaignInvoicePreviewSerializer, InvoiceSerializer
from apps.billing.services import InvoiceService
from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, FINANCE, POE_REVIEWER, SALES
from core.viewsets import ServiceModelViewSet

from .serializers import (
    CampaignAccessTokenCreateSerializer,
    CampaignAccessTokenCreateResponseSerializer,
    CampaignAccessTokenSerializer,
    CampaignAssetSerializer,
    CampaignSerializer,
    CampaignSummarySerializer,
    PublicCampaignAccessSerializer,
)
from .models import Campaign
from .services import (
    CampaignAccessTokenService,
    CampaignAssetService,
    CampaignService,
    PublicCampaignAccessError,
    annotate_campaign_effective_status,
)


class CampaignViewSet(ServiceModelViewSet):
    serializer_class = CampaignSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignService
    allowed_roles = ALL_ROLES + (POE_REVIEWER,)
    write_roles = (ADMIN, SALES)
    write_roles_by_action = {"generate_invoice": (ADMIN, FINANCE)}
    filterset_fields = ["status", "client", "account_manager"]
    search_fields = ["name", "code", "client__email", "account_manager__email"]
    ordering_fields = ["start_date", "end_date", "budget", "created_at", "id"]

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        effective_status = self.request.query_params.get("effective_status")
        if not effective_status:
            return queryset

        normalized = effective_status.lower()
        valid_statuses = {choice.value for choice in Campaign.EffectiveStatus}
        if normalized not in valid_statuses:
            return queryset.none()
        return annotate_campaign_effective_status(queryset).filter(effective_lifecycle=normalized)

    @extend_schema(responses=CampaignSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        summary = self.get_service().get_summary(user=request.user)
        return Response(CampaignSummarySerializer(instance=summary).data)

    @extend_schema(responses=CampaignInvoicePreviewSerializer)
    @action(detail=True, methods=["get"], url_path="invoice-preview")
    def invoice_preview(self, request, pk=None):
        campaign = self.get_object()
        preview = InvoiceService().preview_for_campaign(campaign=campaign)
        return Response(CampaignInvoicePreviewSerializer(instance=preview).data)

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="generate-invoice")
    def generate_invoice(self, request, pk=None):
        campaign = self.get_object()
        invoice = InvoiceService().generate_for_campaign(actor=request.user, campaign=campaign)
        return Response(InvoiceSerializer(instance=invoice, context={"request": request}).data, status=status.HTTP_201_CREATED)


class CampaignAssetViewSet(ServiceModelViewSet):
    serializer_class = CampaignAssetSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignAssetService
    allowed_roles = ALL_ROLES + (POE_REVIEWER,)
    write_roles = (ADMIN, SALES)
    filterset_fields = ["campaign", "asset_type", "is_approved"]
    search_fields = ["name", "campaign__name", "campaign__code"]
    ordering_fields = ["created_at", "name"]


class CampaignAccessTokenViewSet(ServiceModelViewSet):
    serializer_class = CampaignAccessTokenSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignAccessTokenService
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)
    filterset_fields = ["campaign", "is_active"]
    ordering_fields = ["created_at", "expires_at", "last_accessed_at"]

    def create(self, request, *args, **kwargs):
        serializer = CampaignAccessTokenCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        access_token, _raw_token, created = self.get_service().create_token(
            campaign=serializer.validated_data["campaign"],
            actor=request.user,
            expires_at=serializer.validated_data.get("expires_at"),
        )
        response_payload = CampaignAccessTokenCreateResponseSerializer(instance=access_token).data
        return Response(response_payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        access_token = self.get_object()
        self.get_service().revoke(access_token, actor=request.user)
        return Response(CampaignAccessTokenSerializer(instance=access_token).data, status=status.HTTP_200_OK)


class PublicCampaignAccessView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_campaign"

    @extend_schema(responses=PublicCampaignAccessSerializer)
    def get(self, request, token, *args, **kwargs):
        service = CampaignAccessTokenService()

        try:
            access_token, campaign = service.resolve_public_campaign(token)
        except PublicCampaignAccessError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)

        payload = {
            "campaign": campaign,
            "access_expires_at": service.get_effective_expiry(access_token),
            "link_status": "active",
        }
        return Response(PublicCampaignAccessSerializer(instance=payload, context={"request": request}).data)
