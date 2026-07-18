import uuid

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .models import AuthRefreshSession


class RollingJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        authenticated = super().authenticate(request)
        if authenticated is None:
            return None

        user, validated_token = authenticated
        session_id = validated_token.get("sid")
        if not session_id:
            return authenticated

        try:
            parsed_session_id = uuid.UUID(str(session_id))
        except ValueError as exc:
            raise AuthenticationFailed("Invalid session.", code="session_invalid") from exc

        try:
            session = AuthRefreshSession.objects.select_related("user").get(id=parsed_session_id, user=user)
        except AuthRefreshSession.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid session.", code="session_invalid") from exc

        if not session.is_active_session():
            raise AuthenticationFailed("Session expired.", code="session_expired")

        session.touch()
        return authenticated
