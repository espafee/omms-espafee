import time

from django.conf import settings
from django.http import JsonResponse
from django.db import connection
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.roles import ADMIN

from .models import OperationalMode
from .services import get_operational_mode, log_api_request


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class OperationalModeMiddleware:
    exempt_prefixes = (
        "/api/v1/users/auth/",
        "/api/v1/observability/operational-mode/",
        "/api/v1/observability/diagnostics/",
        "/api/v1/observability/health/",
        "/health/",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_authentication = JWTAuthentication()

    def __call__(self, request):
        if self._should_block_request(request):
            mode = get_operational_mode()
            label = mode.get_mode_display()
            return JsonResponse(
                {
                    "detail": mode.message or f"OMMS is currently in {label.lower()} mode.",
                    "code": "operational_mode_blocked",
                    "mode": mode.mode,
                    "label": label,
                },
                status=423 if mode.mode == OperationalMode.Mode.READ_ONLY else 503,
            )
        return self.get_response(request)

    def _should_block_request(self, request) -> bool:
        if request.method in SAFE_METHODS:
            return False
        path = request.path or ""
        if not path.startswith("/api/"):
            return False
        if any(path.startswith(prefix) for prefix in self.exempt_prefixes):
            return False
        try:
            mode = get_operational_mode()
        except Exception:
            return False
        if mode.mode not in {OperationalMode.Mode.MAINTENANCE, OperationalMode.Mode.READ_ONLY}:
            return False
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            try:
                authenticated = self.jwt_authentication.authenticate(request)
            except Exception:
                authenticated = None
            if authenticated:
                user = authenticated[0]
                request.user = user
        return not bool(user and getattr(user, "is_authenticated", False) and (getattr(user, "is_superuser", False) or getattr(user, "role", "") == ADMIN))


class ApiRequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        query_start_count = len(connection.queries) if settings.DEBUG or getattr(settings, "OMMS_QUERY_TIMING_ENABLED", False) else None
        response = self.get_response(request)
        duration_ms = int((time.perf_counter() - started_at) * 1000)

        if not self._should_log(request):
            return response

        query_count = None
        query_time_ms = None
        if query_start_count is not None:
            request_queries = connection.queries[query_start_count:]
            query_count = len(request_queries)
            try:
                query_time_ms = int(sum(float(item.get("time", 0)) for item in request_queries) * 1000)
            except Exception:
                query_time_ms = None

        try:
            log_api_request(
                request=request,
                response=response,
                duration_ms=duration_ms,
                query_count=query_count,
                query_time_ms=query_time_ms,
            )
        except Exception:
            pass
        return response

    def _should_log(self, request) -> bool:
        if not getattr(settings, "OMMS_API_REQUEST_LOGGING_ENABLED", True):
            return False
        path = request.path or ""
        if not path.startswith("/api/"):
            return False
        ignored_prefixes = getattr(settings, "OMMS_REQUEST_LOG_IGNORE_PREFIXES", ())
        return not any(path.startswith(prefix) for prefix in ignored_prefixes)
