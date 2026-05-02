from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.poe.exceptions import DuplicateProofOfExecutionError

from .admin_services import MobileAdminOperationsService
from .permissions import IsMobileAdmin
from .serializers import (
    AssignedWorkSerializer,
    MobileAdminAlertSerializer,
    MobileAdminDailyActivitySerializer,
    MobileAdminOverviewSerializer,
    MobileAdminPoeTrackerSerializer,
    MobileAdminRunningCampaignSerializer,
    MobilePoeSubmitResponseSerializer,
    MobilePoeSubmitSerializer,
)
from .services import MobileWorkService


class AssignedWorkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = AssignedWorkSerializer(MobileWorkService.get_assigned_work(request.user), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MobilePoeSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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
