from __future__ import annotations

from rest_framework import generics, parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ADMIN

from .serializers import (
    CompanyProfileSerializer,
    OrganizationEmailSettingsSerializer,
    SetupUnlockVerifySerializer,
    TestEmailSerializer,
)
from .services import SetupService


class CompanyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = CompanyProfileSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)
    parser_classes = (parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser)

    def get_object(self):
        return SetupService.get_company_profile()


class OrganizationEmailSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = OrganizationEmailSettingsSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)

    def get_object(self):
        return SetupService.get_email_settings()


class OrganizationEmailSettingsTestView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)

    def post(self, request, *args, **kwargs):
        serializer = TestEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipient_email = SetupService.send_test_email(
            recipient_email=serializer.validated_data.get("recipient_email")
        )
        return Response(
            {
                "status": "sent",
                "recipient_email": recipient_email,
            },
            status=status.HTTP_200_OK,
        )


class SetupStatusView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)

    def get(self, request, *args, **kwargs):
        return Response(SetupService.get_setup_status(), status=status.HTTP_200_OK)


class SetupSubmitView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)

    def post(self, request, *args, **kwargs):
        return Response(SetupService.submit_setup(actor=request.user), status=status.HTTP_200_OK)


class SetupUnlockRequestOtpView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)
    throttle_scope = "setup_otp"

    def post(self, request, *args, **kwargs):
        return Response(SetupService.request_unlock_otp(actor=request.user), status=status.HTTP_200_OK)


class SetupUnlockVerifyOtpView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)
    throttle_scope = "setup_otp"

    def post(self, request, *args, **kwargs):
        serializer = SetupUnlockVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            SetupService.verify_unlock_otp(actor=request.user, otp=serializer.validated_data["otp"]),
            status=status.HTTP_200_OK,
        )


class SetupLockView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)

    def post(self, request, *args, **kwargs):
        return Response(SetupService.lock_setup(actor=request.user), status=status.HTTP_200_OK)
