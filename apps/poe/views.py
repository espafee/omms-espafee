from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, OPERATIONS
from core.viewsets import ServiceModelViewSet

from .exceptions import DuplicateProofOfExecutionError
from .serializers import (
    ProofOfExecutionMediaSerializer,
    ProofOfExecutionApproveRequestSerializer,
    ProofOfExecutionRejectRequestSerializer,
    ProofOfExecutionSerializer,
    ProofOfExecutionVerifyRequestSerializer,
    ProofOfExecutionVerifyResponseSerializer,
)
from .services import ProofOfExecutionMediaService, ProofOfExecutionService


class ProofOfExecutionViewSet(ServiceModelViewSet):
    serializer_class = ProofOfExecutionSerializer
    permission_classes = [RoleBasedPermission]
    service_class = ProofOfExecutionService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    filterset_fields = ["booking", "verification_status", "checked_by", "review_sla_status", "review_due_at"]
    ordering_fields = ["executed_on", "captured_at", "review_due_at", "created_at"]

    def get_throttles(self):
        if getattr(self, "action", None) == "create":
            self.throttle_scope = "uploads"
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except DuplicateProofOfExecutionError as exc:
            return Response(exc.data, status=exc.status_code)

    @action(detail=True, methods=["post"], url_path="quick-approve")
    def quick_approve(self, request, pk=None):
        poe_record = self.get_object()
        serializer = ProofOfExecutionApproveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = self.get_service().approve_record(
            poe_record,
            actor=request.user,
            comment=serializer.validated_data.get("comment", ""),
        )
        return Response(self.get_serializer(updated).data)

    @action(detail=True, methods=["post"], url_path="quick-reject")
    def quick_reject(self, request, pk=None):
        poe_record = self.get_object()
        serializer = ProofOfExecutionRejectRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = self.get_service().reject_record(
            poe_record,
            actor=request.user,
            reason=serializer.validated_data.get("reason", ""),
            comment=serializer.validated_data.get("comment", ""),
        )
        return Response(self.get_serializer(updated).data)


class ProofOfExecutionMediaViewSet(ServiceModelViewSet):
    serializer_class = ProofOfExecutionMediaSerializer
    permission_classes = [RoleBasedPermission]
    service_class = ProofOfExecutionMediaService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["poe_record", "media_type"]
    ordering_fields = ["captured_at", "created_at"]

    def get_throttles(self):
        if getattr(self, "action", None) in {"create", "update", "partial_update"}:
            self.throttle_scope = "uploads"
        return super().get_throttles()


class ProofOfExecutionVerifyView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, OPERATIONS)

    def post(self, request, *args, **kwargs):
        serializer = ProofOfExecutionVerifyRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        poe_record = serializer.validated_data["poe_record"]
        threshold = serializer.validated_data["distance_threshold_meters"]

        service = ProofOfExecutionService()
        if not service.has_object_access(request.user, poe_record):
            self.permission_denied(request, message="You do not have permission to verify this POE record.")

        result = service.verify_record(
            poe_record,
            actor=request.user,
            distance_threshold_meters=threshold,
        )

        response_serializer = ProofOfExecutionVerifyResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
