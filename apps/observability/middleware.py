import time

from django.conf import settings
from django.db import connection

from .services import log_api_request


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
