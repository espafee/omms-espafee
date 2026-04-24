from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, SALES
from core.viewsets import ServiceModelViewSet

from .serializers import (
    CampaignAccessTokenCreateSerializer,
    CampaignAccessTokenSerializer,
    CampaignAssetSerializer,
    CampaignSerializer,
    CampaignSummarySerializer,
    PublicCampaignAccessSerializer,
)
from .services import CampaignAccessTokenService, CampaignAssetService, CampaignService, PublicCampaignAccessError


class CampaignViewSet(ServiceModelViewSet):
    serializer_class = CampaignSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, SALES)
    filterset_fields = ["status", "client", "account_manager"]
    search_fields = ["name", "code", "client__email", "account_manager__email"]
    ordering_fields = ["start_date", "end_date", "budget", "created_at"]

    @extend_schema(responses=CampaignSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        summary = self.get_service().get_summary(user=request.user)
        return Response(CampaignSummarySerializer(instance=summary).data)


class CampaignAssetViewSet(ServiceModelViewSet):
    serializer_class = CampaignAssetSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignAssetService
    allowed_roles = ALL_ROLES
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
        serializer = CampaignAccessTokenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token, raw_token = self.get_service().create_token(
            campaign=serializer.validated_data["campaign"],
            actor=request.user,
            expires_at=serializer.validated_data.get("expires_at"),
        )
        response_payload = CampaignAccessTokenSerializer(instance=access_token).data
        response_payload["token"] = raw_token
        response_payload["public_path"] = f"/campaigns/public/{raw_token}"
        return Response(response_payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        access_token = self.get_object()
        self.get_service().revoke(access_token, actor=request.user)
        return Response(CampaignAccessTokenSerializer(instance=access_token).data, status=status.HTTP_200_OK)


class PublicCampaignAccessView(APIView):
    permission_classes = [AllowAny]

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
