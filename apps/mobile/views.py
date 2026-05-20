from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.poe.exceptions import DuplicateProofOfExecutionError
from apps.observability.services import build_operational_mode_payload, build_operational_search

from .admin_services import MobileAdminOperationsService
from .permissions import IsMobileAdmin
from .serializers import (
    AssignedWorkSerializer,
    MobileAdminAlertSerializer,
    MobileAdminDailyActivitySerializer,
    MobileAdminIssueSerializer,
    MobileAdminOverviewSerializer,
    MobileAdminPoeTrackerSerializer,
    MobileAdminRunningCampaignSerializer,
    MobileAdminSearchResultSerializer,
    MobileEnvironmentModeSerializer,
    MobilePoeSubmitResponseSerializer,
    MobilePoeSubmitSerializer,
)
from .services import MobileWorkService


class AssignedWorkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = AssignedWorkSerializer(MobileWorkService.get_assigned_work(request.user), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileEnvironmentModeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = MobileEnvironmentModeSerializer(build_operational_mode_payload())
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobilePoeSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "uploads"

    def post(self, request, *args, **kwargs):
        serializer = MobilePoeSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = MobileWorkService.submit_poe(user=request.user, **serializer.validated_data)
        except DuplicateProofOfExecutionError as exc:
            return Response(exc.data, status=exc.status_code)
        response_serializer = MobilePoeSubmitResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class MobileAdminOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        serializer = MobileAdminOverviewSerializer(MobileAdminOperationsService.get_overview())
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileAdminRunningCampaignsView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        serializer = MobileAdminRunningCampaignSerializer(MobileAdminOperationsService.get_running_campaigns(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileAdminPoeTrackerView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        serializer = MobileAdminPoeTrackerSerializer(
            MobileAdminOperationsService.get_poe_tracker(
                status_filter=request.query_params.get("status"),
                request=request,
            ),
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileAdminDailyActivityView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        serializer = MobileAdminDailyActivitySerializer(MobileAdminOperationsService.get_daily_activity())
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileAdminAlertsView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        serializer = MobileAdminAlertSerializer(MobileAdminOperationsService.get_alerts(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobileAdminSearchView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        query_params = request.query_params.copy()
        query_params["modules"] = query_params.get("modules") or "campaigns,sites,units"
        payload = build_operational_search(request.user, query_params)
        serializer = MobileAdminSearchResultSerializer(payload["results"][:10], many=True)
        return Response({"query": payload["query"], "results": serializer.data}, status=status.HTTP_200_OK)


class MobileAdminIssuesView(APIView):
    permission_classes = [IsAuthenticated, IsMobileAdmin]

    def get(self, request, *args, **kwargs):
        serializer = MobileAdminIssueSerializer(
            MobileAdminOperationsService.get_issues(request=request),
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
