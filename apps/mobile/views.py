from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AssignedWorkSerializer, MobilePoeSubmitResponseSerializer, MobilePoeSubmitSerializer
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
        result = MobileWorkService.submit_poe(user=request.user, **serializer.validated_data)
        response_serializer = MobilePoeSubmitResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
