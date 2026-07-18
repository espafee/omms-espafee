from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenVerifyView

from core.permissions import RoleBasedPermission
from core.roles import ADMIN, FIELD_ASSIGNABLE_ROLES, SALES
from core.viewsets import ServiceModelViewSet
from apps.tenants.services import scope_users_to_requesting_tenant

from .serializers import (
    ClientCreateSerializer,
    ClientOptionSerializer,
    CustomTokenObtainPairSerializer,
    FieldStaffOptionSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .session_auth import (
    RefreshSessionError,
    clear_refresh_cookie,
    create_refresh_session,
    create_session_from_legacy_refresh,
    get_refresh_session,
    response_payload_for_session,
    revoke_refresh_session,
    set_refresh_cookie,
    touch_refresh_session,
)
from .services import UserService

User = get_user_model()


class UserViewSet(ServiceModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [RoleBasedPermission]
    service_class = UserService
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "username", "first_name", "last_name", "organization_name"]
    ordering_fields = ["created_at", "email", "first_name"]
    http_method_names = ["get", "patch", "head", "options"]

    def partial_update(self, request, *args, **kwargs):
        protected_fields = {"role", "tenant", "is_active", "is_staff", "is_superuser"}
        attempted_fields = sorted(protected_fields.intersection(request.data))
        if attempted_fields:
            raise ValidationError(
                {
                    "detail": [
                        "Role, company, activation, and privilege changes must use the audited Team & access workflow."
                    ],
                    "protected_fields": attempted_fields,
                }
            )
        return super().partial_update(request, *args, **kwargs)


class ClientDirectoryView(generics.ListCreateAPIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN, SALES)
    write_roles = (ADMIN,)

    def get_queryset(self):
        queryset = User.objects.filter(role=User.Role.CLIENT)
        return scope_users_to_requesting_tenant(queryset, self.request.user).order_by("organization_name", "email")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ClientCreateSerializer
        return ClientOptionSerializer


class FieldStaffDirectoryView(generics.ListAPIView):
    serializer_class = FieldStaffOptionSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN, SALES)

    def get_queryset(self):
        queryset = User.objects.filter(role__in=FIELD_ASSIGNABLE_ROLES, is_active=True)
        return scope_users_to_requesting_tenant(queryset, self.request.user).order_by("first_name", "email")


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    throttle_scope = "registration"

    def create(self, request, *args, **kwargs):
        if not settings.OMMS_PUBLIC_REGISTRATION_ENABLED:
            return Response(
                {
                    "detail": "Public registration is disabled. Ask an OMMS administrator to create or invite this user."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = "auth_token"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session, cookie_value = create_refresh_session(serializer.user, request)
        response = Response(response_payload_for_session(session), status=status.HTTP_200_OK)
        set_refresh_cookie(response, cookie_value)
        return response


class CustomTokenRefreshView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_token"

    def post(self, request, *args, **kwargs):
        cookie_value = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        try:
            session = get_refresh_session(cookie_value)
            touch_refresh_session(session)
            response = Response(response_payload_for_session(session), status=status.HTTP_200_OK)
            if cookie_value:
                set_refresh_cookie(response, cookie_value)
            return response
        except RefreshSessionError:
            legacy_refresh = request.data.get("refresh") if isinstance(request.data, dict) else None
            if not legacy_refresh:
                response = Response(
                    {"detail": "Refresh session expired. Please sign in again.", "code": "session_expired"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                clear_refresh_cookie(response)
                return response
            try:
                session, next_cookie_value = create_session_from_legacy_refresh(str(legacy_refresh), request)
            except (RefreshSessionError, TokenError, InvalidToken, User.DoesNotExist):
                response = Response(
                    {"detail": "Refresh session expired. Please sign in again.", "code": "session_expired"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                clear_refresh_cookie(response)
                return response
            response = Response(response_payload_for_session(session), status=status.HTTP_200_OK)
            set_refresh_cookie(response, next_cookie_value)
            return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth_token"

    def post(self, request, *args, **kwargs):
        revoke_refresh_session(request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME))
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class CustomTokenVerifyView(TokenVerifyView):
    throttle_scope = "auth_token"


class AuthHealthView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({"authenticated": True, "user_id": request.user.id})
