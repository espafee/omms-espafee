from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, OPERATIONS
from core.viewsets import ServiceModelViewSet

from .exceptions import DuplicateProofOfExecutionError
from .serializers import (
    ProofOfExecutionMediaSerializer,
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
    filterset_fields = ["booking", "verification_status", "checked_by"]
    ordering_fields = ["executed_on", "captured_at", "created_at"]

    def get_throttles(self):
        if getattr(self, "action", None) == "create":
            self.throttle_scope = "uploads"
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except DuplicateProofOfExecutionError as exc:
            return Response(exc.data, status=exc.status_code)


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
        serializer = ProofOfExecutionVerifyRequestSerializer(data=request.data)
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
