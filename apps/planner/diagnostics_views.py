from __future__ import annotations

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.services import is_platform_super_admin

from .diagnostics import MediaPlannerDiagnosticsRequest, MediaPlannerDiagnosticsService
from .models import MediaPlannerShareLink
from .services import InventoryAvailabilityService
from .views import _parse_date


class MediaPlannerPlatformDiagnosticsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "platform_diagnostics"

    def get(self, request):
        if not getattr(settings, "ENABLE_PLATFORM_DIAGNOSTICS", False):
            raise NotFound("Platform diagnostics are disabled.")
        if not is_platform_super_admin(request.user):
            raise PermissionDenied("Only platform superadmins can access media planner diagnostics.")

        link = self._resolve_link(request)
        start_date = _parse_date(request.query_params.get("requested_start_date"))
        end_date = _parse_date(request.query_params.get("requested_end_date"))
        try:
            InventoryAvailabilityService().validate_dates(start_date, end_date)
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        unit_codes = tuple(
            dict.fromkeys(
                code.strip()
                for code in request.query_params.get("unit_code", "").replace("\n", ",").split(",")
                if code.strip()
            )
        )
        payload = MediaPlannerDiagnosticsService().build(
            MediaPlannerDiagnosticsRequest(
                link=link,
                unit_codes=unit_codes,
                start_date=start_date,
                end_date=end_date,
            )
        )
        return Response(payload)

    def _resolve_link(self, request):
        planner_link_id = request.query_params.get("planner_link_id", "").strip()
        planner_title = request.query_params.get("planner_title", "").strip()
        if not planner_link_id and not planner_title:
            raise ValidationError({"planner_link": ["Provide planner_link_id or planner_title."]})

        queryset = MediaPlannerShareLink.objects.select_related("tenant", "client", "created_by")
        if planner_link_id:
            if not planner_link_id.isdigit():
                raise ValidationError({"planner_link_id": ["Use a numeric planner link id."]})
            link = queryset.filter(pk=int(planner_link_id)).first()
            if not link:
                raise NotFound("Planner link was not found.")
            return link

        matches = list(queryset.filter(Q(title__iexact=planner_title) | Q(title__icontains=planner_title))[:2])
        if not matches:
            raise NotFound("Planner link was not found.")
        if len(matches) > 1:
            raise ValidationError({"planner_title": ["More than one planner link matched. Use planner_link_id."]})
        return matches[0]

