from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiRequestLogViewSet,
    AuditEventViewSet,
    DiagnosticsView,
    ImportExportJobViewSet,
    PoeAnalyticsView,
    RoleActivityView,
)

router = DefaultRouter()
router.register("request-logs", ApiRequestLogViewSet, basename="observability-request-logs")
router.register("audit-events", AuditEventViewSet, basename="observability-audit-events")
router.register("import-export-jobs", ImportExportJobViewSet, basename="observability-import-export-jobs")

urlpatterns = [
    path("poe-analytics/", PoeAnalyticsView.as_view(), name="observability-poe-analytics"),
    path("diagnostics/", DiagnosticsView.as_view(), name="observability-diagnostics"),
    path("role-activity/", RoleActivityView.as_view(), name="observability-role-activity"),
] + router.urls
