from datetime import date

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Assignment
from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, OPERATIONS, POE_REVIEWER
from core.viewsets import ServiceModelViewSet

from .exceptions import DuplicateProofOfExecutionError
from .models import ProofOfExecution
from .serializers import (
    ProofOfExecutionApproveRequestSerializer,
    ProofOfExecutionMediaSerializer,
    ProofOfExecutionRejectRequestSerializer,
    ProofOfExecutionSerializer,
    ProofOfExecutionVerifyRequestSerializer,
    ProofOfExecutionVerifyResponseSerializer,
)
from .services import ProofOfExecutionMediaService, ProofOfExecutionService

FIELD_UPLOAD_SALT = "omms.field-poe-upload"
FIELD_UPLOAD_MAX_AGE = int(getattr(settings, "FIELD_POE_UPLOAD_MAX_AGE_SECONDS", 7 * 24 * 60 * 60))


def _load_field_token(token):
    try:
        payload = signing.loads(token, salt=FIELD_UPLOAD_SALT, max_age=FIELD_UPLOAD_MAX_AGE)
    except signing.SignatureExpired as exc:
        raise ValueError("This upload link has expired.") from exc
    except signing.BadSignature as exc:
        raise ValueError("This upload link is invalid.") from exc
    assignment = get_object_or_404(
        Assignment.objects.select_related(
            "booking__campaign",
            "booking__media_unit__site",
            "user",
        ),
        pk=payload.get("assignment_id"),
    )
    if assignment.status == Assignment.Status.CANCELLED:
        raise ValueError("This upload link has been revoked.")
    return assignment


def _assignment_payload(assignment):
    booking = assignment.booking
    unit = booking.media_unit
    site = unit.site
    return {
        "assignment_id": assignment.id,
        "status": assignment.status,
        "campaign": {"id": booking.campaign_id, "name": booking.campaign.name, "code": booking.campaign.code},
        "booking": {"id": booking.id, "start_date": booking.start_date, "end_date": booking.end_date},
        "unit": {"id": unit.id, "code": unit.unit_code, "dimensions": getattr(unit, "dimensions", "")},
        "site": {
            "id": site.id,
            "name": site.name,
            "address": site.address,
            "city": site.city,
            "latitude": site.latitude,
            "longitude": site.longitude,
        },
        "field_executive": assignment.user.get_full_name() or assignment.user.email,
    }


class ProofOfExecutionViewSet(ServiceModelViewSet):
    serializer_class = ProofOfExecutionSerializer
    permission_classes = [RoleBasedPermission]
    service_class = ProofOfExecutionService
    allowed_roles = ALL_ROLES + (POE_REVIEWER,)
    write_roles = (ADMIN, OPERATIONS, POE_REVIEWER)
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
        updated = self.get_service().approve_record(poe_record, actor=request.user, comment=serializer.validated_data.get("comment", ""))
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
    allowed_roles = ALL_ROLES + (POE_REVIEWER,)
    write_roles = (ADMIN, OPERATIONS, POE_REVIEWER)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["poe_record", "media_type"]
    ordering_fields = ["captured_at", "created_at"]

    def get_throttles(self):
        if getattr(self, "action", None) in {"create", "update", "partial_update"}:
            self.throttle_scope = "uploads"
        return super().get_throttles()


class ProofOfExecutionVerifyView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = ALL_ROLES + (POE_REVIEWER,)
    write_roles = (ADMIN, OPERATIONS, POE_REVIEWER)

    def post(self, request, *args, **kwargs):
        serializer = ProofOfExecutionVerifyRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        poe_record = serializer.validated_data["poe_record"]
        threshold = serializer.validated_data["distance_threshold_meters"]
        service = ProofOfExecutionService()
        if not service.has_object_access(request.user, poe_record):
            self.permission_denied(request, message="You do not have permission to verify this POE record.")
        result = service.verify_record(poe_record, actor=request.user, distance_threshold_meters=threshold)
        return Response(ProofOfExecutionVerifyResponseSerializer(result).data, status=status.HTTP_200_OK)


class FieldPoeLinkCreateView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN, OPERATIONS)
    write_roles = (ADMIN, OPERATIONS)

    def post(self, request):
        assignment = get_object_or_404(
            Assignment.objects.select_related("booking__campaign"),
            pk=request.data.get("assignment_id"),
            booking__campaign__tenant=request.user.tenant,
        )
        if assignment.status == Assignment.Status.CANCELLED:
            return Response({"detail": "Cancelled assignments cannot receive upload links."}, status=status.HTTP_400_BAD_REQUEST)
        token = signing.dumps({"assignment_id": assignment.id}, salt=FIELD_UPLOAD_SALT, compress=True)
        return Response({
            "token": token,
            "path": f"/field/poe/{token}",
            "expires_in_seconds": FIELD_UPLOAD_MAX_AGE,
            "assignment": _assignment_payload(assignment),
        })


class PublicFieldPoeUploadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_scope = "uploads"

    def get(self, request, token):
        try:
            assignment = _load_field_token(token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_410_GONE)
        payload = _assignment_payload(assignment)
        payload["submitted"] = assignment.status == Assignment.Status.COMPLETED
        return Response(payload)

    @transaction.atomic
    def post(self, request, token):
        try:
            assignment = _load_field_token(token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_410_GONE)
        if assignment.status == Assignment.Status.COMPLETED:
            return Response({"detail": "POE has already been submitted for this link."}, status=status.HTTP_409_CONFLICT)

        images = request.FILES.getlist("images") or request.FILES.getlist("image")
        if not images:
            return Response({"images": ["At least one execution photo is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            executed_on = date.fromisoformat(request.data.get("executed_on") or timezone.localdate().isoformat())
        except ValueError:
            return Response({"executed_on": ["Enter a valid date."]}, status=status.HTTP_400_BAD_REQUEST)

        poe = ProofOfExecutionService().create(
            actor=None,
            booking=assignment.booking,
            client_upload_id=f"field-assignment-{assignment.id}",
            executed_on=executed_on,
            captured_at=timezone.now(),
            latitude=request.data.get("latitude") or None,
            longitude=request.data.get("longitude") or None,
            notes=(request.data.get("notes") or "").strip(),
        )
        media_service = ProofOfExecutionMediaService()
        for image in images:
            media_service.create(actor=assignment.user, poe_record=poe, image=image, media_type="image", captured_at=timezone.now())

        assignment.status = Assignment.Status.COMPLETED
        assignment.save(update_fields=["status", "updated_at"])
        return Response({"poe_id": poe.id, "reference": f"POE-{poe.id:06d}", "status": poe.verification_status}, status=status.HTTP_201_CREATED)
