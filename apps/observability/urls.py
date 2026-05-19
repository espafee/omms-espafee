from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertEventViewSet,
    AlertRuleViewSet,
    ApiRequestLogViewSet,
    AuditEventViewSet,
    DiagnosticsView,
    EvaluateAlertsView,
    HealthView,
    ImportExportJobViewSet,
    OperationalSearchView,
    OperationsSummaryView,
    PoeAnalyticsView,
    RoleActivityView,
    SavedOperationalViewViewSet,
)

router = DefaultRouter()
router.register("request-logs", ApiRequestLogViewSet, basename="observability-request-logs")
router.register("audit-events", AuditEventViewSet, basename="observability-audit-events")
router.register("import-export-jobs", ImportExportJobViewSet, basename="observability-import-export-jobs")
router.register("alert-rules", AlertRuleViewSet, basename="observability-alert-rules")
router.register("alert-events", AlertEventViewSet, basename="observability-alert-events")
router.register("saved-views", SavedOperationalViewViewSet, basename="observability-saved-views")

urlpatterns = [
    path("poe-analytics/", PoeAnalyticsView.as_view(), name="observability-poe-analytics"),
    path("operations-summary/", OperationsSummaryView.as_view(), name="observability-operations-summary"),
    path("operational-search/", OperationalSearchView.as_view(), name="observability-operational-search"),
    path("diagnostics/", DiagnosticsView.as_view(), name="observability-diagnostics"),
    path("health/", HealthView.as_view(), name="observability-health"),
    path("evaluate-alerts/", EvaluateAlertsView.as_view(), name="observability-evaluate-alerts"),
    path("role-activity/", RoleActivityView.as_view(), name="observability-role-activity"),
] + router.urls
