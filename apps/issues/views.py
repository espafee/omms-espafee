from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.viewsets import ModelViewSet

from apps.bookings.models import Assignment
from core.roles import FIELD_STAFF

from .models import Issue
from .serializers import IssueSerializer, is_admin_like_user


class IssuePermission(BasePermission):
    message = "You do not have permission to access issues."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_admin_like_user(user):
            return True
        if view.action == "create" and getattr(user, "role", None) == FIELD_STAFF:
            return True
        if view.action in {"list", "retrieve"} and getattr(user, "role", None) == FIELD_STAFF:
            return True
        return False

    def has_object_permission(self, request, view, obj):
        if is_admin_like_user(request.user):
            return True
        if getattr(request.user, "role", None) == FIELD_STAFF and request.method in {"GET", "HEAD", "OPTIONS"}:
            return obj.reported_by_id == request.user.id
        return False


class IssueViewSet(ModelViewSet):
    serializer_class = IssueSerializer
    permission_classes = [IssuePermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["status", "priority", "issue_type", "booking"]
    search_fields = ["description", "booking__campaign__name", "booking__media_unit__site__name"]
    ordering_fields = ["created_at", "priority", "status", "resolved_at"]

    def get_queryset(self):
        queryset = Issue.objects.select_related(
            "booking",
            "booking__campaign",
            "booking__media_unit",
            "booking__media_unit__site",
            "assignment",
            "assignment__user",
            "reported_by",
        )
        if is_admin_like_user(self.request.user):
            return queryset
        return queryset.filter(reported_by=self.request.user)

    def perform_create(self, serializer):
        booking = serializer.validated_data["booking"]
        assignment = (
            booking.assignments.filter(
                user=self.request.user,
                status__in=[Assignment.Status.PENDING, Assignment.Status.COMPLETED],
            )
            .order_by("-assigned_at")
            .first()
        )
        if is_admin_like_user(self.request.user) and assignment is None:
            assignment = booking.assignments.exclude(status=Assignment.Status.CANCELLED).order_by("-assigned_at").first()

        serializer.save(
            reported_by=self.request.user,
            assignment=assignment,
        )
