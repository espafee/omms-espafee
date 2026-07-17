from django.contrib.auth import get_user_model
from django.core.mail import BadHeaderError
from django.http import Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .team_serializers import (
    PasswordSetupCompleteSerializer,
    TeamRolesSerializer,
    TeamUserSerializer,
    TeamUserWriteSerializer,
)
from .team_services import (
    can_manage_team,
    create_team_user,
    record_prohibited_team_action,
    send_team_setup_email,
    set_team_user_active,
    team_user_queryset,
    update_team_user,
)

User = get_user_model()


class CanManageTeam(BasePermission):
    message = "Only platform or company administrators can manage team access."

    def has_permission(self, request, view):
        return can_manage_team(request.user)


class TeamUserViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, CanManageTeam]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["role", "is_active", "region", "tenant"]
    search_fields = ["email", "first_name", "last_name", "region"]
    ordering_fields = ["created_at", "email", "first_name", "last_login"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        return team_user_queryset(self.request.user)

    def get_serializer_class(self):
        if self.action in {"create", "partial_update", "update"}:
            return TeamUserWriteSerializer
        return TeamUserSerializer

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            target_id = self.kwargs.get(self.lookup_field or "pk")
            if target_id and User.objects.filter(pk=target_id).exists():
                record_prohibited_team_action(
                    actor=self.request.user,
                    target_id=target_id,
                    reason="cross_tenant_object_access",
                )
            raise

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        send_setup = values.pop("send_setup", True)
        user = create_team_user(actor=request.user, **values)
        setup_delivery = "not_requested"
        if send_setup:
            try:
                send_team_setup_email(actor=request.user, target=user)
                setup_delivery = "sent"
            except (BadHeaderError, OSError, RuntimeError, ConnectionError):
                setup_delivery = "failed"
        payload = TeamUserSerializer(user).data
        payload["setup_delivery"] = setup_delivery
        return Response(payload, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        target = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True, context={"request": request, "instance": target})
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        values.pop("send_setup", None)
        updated = update_team_user(actor=request.user, target=target, **values)
        return Response(TeamUserSerializer(updated).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE",
            detail="Team members are deactivated instead of deleted so historical activity remains intact.",
        )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        target = self.get_object()
        updated = set_team_user_active(actor=request.user, target=target, is_active=False)
        return Response(TeamUserSerializer(updated).data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        target = self.get_object()
        updated = set_team_user_active(actor=request.user, target=target, is_active=True)
        return Response(TeamUserSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="send-setup")
    def send_setup(self, request, pk=None):
        target = self.get_object()
        try:
            updated = send_team_setup_email(actor=request.user, target=target)
        except (BadHeaderError, OSError, RuntimeError, ConnectionError):
            return Response(
                {"detail": "Account setup could not be sent. Check email configuration and try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(TeamUserSerializer(updated).data)


class TeamRolesView(APIView):
    permission_classes = [IsAuthenticated, CanManageTeam]

    def get(self, request):
        return Response(TeamRolesSerializer.for_actor(request.user))


class PasswordSetupCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_token"

    def post(self, request):
        serializer = PasswordSetupCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "detail": "Password set successfully. You can now sign in."
                if user.is_active
                else "Password set successfully. Ask your company administrator to restore account access.",
                "is_active": user.is_active,
            }
        )
