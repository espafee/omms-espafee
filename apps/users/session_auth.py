from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import AuthRefreshSession

SESSION_TOKEN_BYTES = 32
SESSION_COOKIE_SEPARATOR = "."


class RefreshSessionError(Exception):
    pass


def _hash_session_secret(secret: str) -> str:
    return salted_hmac("omms.auth.refresh_session", secret, secret=settings.SECRET_KEY).hexdigest()


def _client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _user_agent(request) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:1000]


def _cookie_domain() -> str | None:
    return settings.AUTH_REFRESH_COOKIE_DOMAIN or None


def create_refresh_session(user, request) -> tuple[AuthRefreshSession, str]:
    secret = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    session = AuthRefreshSession.objects.create(
        user=user,
        token_hash=_hash_session_secret(secret),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    return session, f"{session.id}{SESSION_COOKIE_SEPARATOR}{secret}"


def get_refresh_session(cookie_value: str | None) -> AuthRefreshSession:
    if not cookie_value or SESSION_COOKIE_SEPARATOR not in cookie_value:
        raise RefreshSessionError("missing_refresh_session")
    raw_session_id, secret = cookie_value.split(SESSION_COOKIE_SEPARATOR, 1)
    try:
        session_id = uuid.UUID(raw_session_id)
    except ValueError as exc:
        raise RefreshSessionError("invalid_refresh_session") from exc

    try:
        session = AuthRefreshSession.objects.select_related("user", "user__tenant").get(id=session_id)
    except AuthRefreshSession.DoesNotExist as exc:
        raise RefreshSessionError("invalid_refresh_session") from exc

    if not constant_time_compare(session.token_hash, _hash_session_secret(secret)):
        raise RefreshSessionError("invalid_refresh_session")
    if not session.is_active_session():
        raise RefreshSessionError("expired_refresh_session")
    return session


def revoke_refresh_session(cookie_value: str | None) -> None:
    try:
        session = get_refresh_session(cookie_value)
    except RefreshSessionError:
        return
    session.revoke()


def touch_refresh_session(session: AuthRefreshSession) -> None:
    if session.is_active_session():
        session.touch()


def add_user_claims(token, user, session: AuthRefreshSession | None = None):
    token["email"] = user.email
    token["role"] = user.role
    token["tenant_id"] = user.tenant_id
    token["tenant_slug"] = user.tenant.slug if user.tenant_id else ""
    token["tenant_type"] = user.tenant.tenant_type if user.tenant_id else ""
    token["is_platform_admin"] = user.is_platform_admin
    token["is_company_admin"] = user.is_company_admin
    token["is_staff"] = user.is_staff
    token["is_superuser"] = user.is_superuser
    if session is not None:
        token["sid"] = str(session.id)
    return token


def issue_access_token(user, session: AuthRefreshSession | None = None) -> str:
    token = AccessToken.for_user(user)
    add_user_claims(token, user, session)
    return str(token)


def response_payload_for_session(session: AuthRefreshSession) -> dict:
    from .serializers import UserSerializer

    return {
        "access": issue_access_token(session.user, session),
        "user": UserSerializer(session.user).data,
        "expires_in": settings.ACCESS_TOKEN_LIFETIME_MINUTES * 60,
        "session_expires_at": session.expires_at().isoformat(),
    }


def set_refresh_cookie(response, cookie_value: str) -> None:
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        cookie_value,
        max_age=settings.REFRESH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        domain=_cookie_domain(),
        path="/",
    )


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        domain=_cookie_domain(),
        path="/",
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


def create_session_from_legacy_refresh(refresh_token: str, request) -> tuple[AuthRefreshSession, str]:
    token = RefreshToken(refresh_token)
    user_id = token.get("user_id")
    user = get_user_model().objects.select_related("tenant").get(id=user_id)
    if not user.is_active:
        raise RefreshSessionError("inactive_user")
    return create_refresh_session(user, request)
