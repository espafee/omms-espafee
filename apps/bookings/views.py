from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.issues.models import IssueReportToken
from apps.issues.services import build_public_issue_report_url
from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, POE_REVIEWER, SALES
from core.viewsets import ServiceModelViewSet

from .serializers import BookingSerializer, BookingSummarySerializer
from .services import BookingService


class BookingViewSet(ServiceModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [RoleBasedPermission]
    service_class = BookingService
    allowed_roles = ALL_ROLES + (POE_REVIEWER,)
    write_roles = (ADMIN, SALES)
    write_roles_by_action = {"issue_report_token": (ADMIN,)}
    filterset_fields = ["status", "campaign", "media_unit"]
    search_fields = ["campaign__name", "campaign__code", "media_unit__unit_code"]
    ordering_fields = ["start_date", "end_date", "booked_rate", "created_at"]

    @extend_schema(responses=BookingSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        summary = self.get_service().get_summary(user=request.user)
        return Response(BookingSummarySerializer(instance=summary).data)

    @action(detail=True, methods=["post"], url_path="issue-report-token")
    def issue_report_token(self, request, pk=None):
        booking = self.get_object()
        token_record = IssueReportToken.objects.create(
            booking=booking,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        return Response(
            {
                "token": token_record.token,
                "expires_at": token_record.expires_at,
                "public_url": build_public_issue_report_url(token_record.token),
            }
        )
