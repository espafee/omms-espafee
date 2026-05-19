import logging

from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ADMIN, ALL_ROLES, FINANCE, OPERATIONS
from core.viewsets import ServiceModelViewSet

from .models import AlertEvent, AlertRule, ApiRequestLog, AuditEvent, ImportExportJob, SavedOperationalView
from .serializers import (
    AlertEventSerializer,
    AlertRuleSerializer,
    ApiRequestLogSerializer,
    AuditEventSerializer,
    ImportExportJobSerializer,
    DashboardProfileSerializer,
    OperationalSearchSerializer,
    SavedOperationalViewSerializer,
)
from .services import (
    AlertEventService,
    AlertRuleService,
    ApiRequestLogService,
    AuditEventService,
    ImportExportJobService,
    build_dashboard_profile,
    build_diagnostics_payload,
    build_empty_operations_summary,
    build_operations_summary,
    build_operational_search,
    build_poe_analytics,
    build_role_activity,
    confirm_inventory_sites_import,
    evaluate_alert_thresholds,
    export_campaigns_csv,
    export_client_statement_csv,
    export_invoices_csv,
    export_inventory_sites_csv,
    export_poe_reports_csv,
    record_audit_event,
    retry_import_export_job,
    reset_dashboard_widget_preferences,
    SavedOperationalViewService,
    save_dashboard_widget_preferences,
    validate_inventory_sites_import,
)


OBSERVABILITY_ROLES = (ADMIN, OPERATIONS, FINANCE)
logger = logging.getLogger(__name__)


class ApiRequestLogViewSet(ServiceModelViewSet):
    serializer_class = ApiRequestLogSerializer
    permission_classes = [RoleBasedPermission]
    service_class = ApiRequestLogService
    allowed_roles = OBSERVABILITY_ROLES
    http_method_names = ["get", "head", "options"]
    filterset_fields = {
        "method": ["exact"],
        "status_code": ["exact", "gte"],
        "is_slow": ["exact"],
        "category": ["exact"],
        "user": ["exact"],
        "created_at": ["gte", "lte"],
    }
    search_fields = ["path", "user_agent", "company_name"]
    ordering_fields = ["created_at", "duration_ms", "status_code", "query_count", "query_time_ms"]


class AuditEventViewSet(ServiceModelViewSet):
    serializer_class = AuditEventSerializer
    permission_classes = [RoleBasedPermission]
    service_class = AuditEventService
    allowed_roles = OBSERVABILITY_ROLES
    http_method_names = ["get", "head", "options"]
    filterset_fields = {
        "event_type": ["exact"],
        "entity_type": ["exact"],
        "entity_id": ["exact"],
        "actor": ["exact"],
        "severity": ["exact"],
        "created_at": ["gte", "lte"],
    }
    search_fields = ["summary", "campaign_reference", "client_reference", "invoice_reference"]
    ordering_fields = ["created_at", "severity", "event_type"]


class ImportExportJobViewSet(ServiceModelViewSet):
    serializer_class = ImportExportJobSerializer
    permission_classes = [RoleBasedPermission]
    service_class = ImportExportJobService
    allowed_roles = OBSERVABILITY_ROLES
    write_roles = (ADMIN, OPERATIONS, FINANCE)
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["job_type", "resource_type", "status", "created_by"]
    search_fields = ["company_name"]
    ordering_fields = ["created_at", "updated_at", "rows_total", "rows_failed"]

    @action(detail=False, methods=["post"], url_path="inventory-sites/import-preview")
    def inventory_sites_import_preview(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"file": ["CSV file is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            job = validate_inventory_sites_import(upload, actor=request.user)
        except ValueError as exc:
            return Response({"file": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"file": ["Unable to parse import file. Check the template and try again."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="inventory-sites/export")
    def inventory_sites_export(self, request):
        job = export_inventory_sites_csv(actor=request.user, filters=request.data)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        try:
            job = confirm_inventory_sites_import(self.get_object(), actor=request.user, confirmed=bool(request.data.get("confirmed")))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"detail": "Unable to start import. Please try again."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        try:
            job = retry_import_export_job(self.get_object(), actor=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"detail": "Unable to retry job. Please try again."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="campaigns/export")
    def campaigns_export(self, request):
        job = export_campaigns_csv(actor=request.user, filters=request.data)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="invoices/export")
    def invoices_export(self, request):
        job = export_invoices_csv(actor=request.user, filters=request.data)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="poe-reports/export")
    def poe_reports_export(self, request):
        job = export_poe_reports_csv(actor=request.user, filters=request.data)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="client-statements/export")
    def client_statements_export(self, request):
        job = export_client_statement_csv(actor=request.user, filters=request.data)
        return Response(self.get_serializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        job = self.get_object()
        file_field = job.output_file or job.original_file
        if not file_field:
            return Response({"detail": "No file is available for this job."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(file_field.open("rb"), as_attachment=True, filename=file_field.name.split("/")[-1])


class PoeAnalyticsView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = OBSERVABILITY_ROLES

    def get(self, request):
        payload = build_poe_analytics(request.query_params)
        return Response(payload)


class DiagnosticsView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)

    def get(self, request):
        return Response(build_diagnostics_payload())


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "omms", "alive": True})


class RoleActivityView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = OBSERVABILITY_ROLES

    def get(self, request):
        return Response(build_role_activity(request.query_params))


class OperationsSummaryView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = OBSERVABILITY_ROLES

    def get(self, request):
        filters = request.query_params.copy()
        filters["_user"] = request.user
        try:
            return Response(build_operations_summary(filters))
        except Exception:
            logger.exception("Operations summary aggregation failed")
            return Response(build_empty_operations_summary(error="Operations summary is temporarily unavailable."))


class DashboardProfileView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = ALL_ROLES

    def get(self, request):
        return Response(DashboardProfileSerializer(build_dashboard_profile(request.user)).data)

    def patch(self, request):
        try:
            payload = save_dashboard_widget_preferences(request.user, request.data.get("widgets", []))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DashboardProfileSerializer(payload).data)

    def post(self, request):
        if request.data.get("action") != "restore_defaults":
            return Response({"detail": "Unsupported dashboard profile action."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DashboardProfileSerializer(reset_dashboard_widget_preferences(request.user)).data)


class OperationalSearchView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = OBSERVABILITY_ROLES

    def get(self, request):
        payload = build_operational_search(request.user, request.query_params)
        return Response(OperationalSearchSerializer(payload).data)


class SavedOperationalViewViewSet(ServiceModelViewSet):
    serializer_class = SavedOperationalViewSerializer
    permission_classes = [RoleBasedPermission]
    service_class = SavedOperationalViewService
    allowed_roles = OBSERVABILITY_ROLES
    write_roles = OBSERVABILITY_ROLES
    filterset_fields = ["view_type", "module", "is_default"]
    search_fields = ["name", "search_query"]
    ordering_fields = ["name", "updated_at", "view_type"]

    def get_queryset(self):
        return super().get_queryset().order_by("view_type", "name")


class EvaluateAlertsView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN,)

    def post(self, request):
        events = evaluate_alert_thresholds()
        return Response({"created_alerts": len(events), "alert_ids": [event.id for event in events]})


class AlertRuleViewSet(ServiceModelViewSet):
    serializer_class = AlertRuleSerializer
    permission_classes = [RoleBasedPermission]
    service_class = AlertRuleService
    allowed_roles = OBSERVABILITY_ROLES
    write_roles = (ADMIN,)
    filterset_fields = ["metric", "severity", "is_enabled"]
    search_fields = ["name"]
    ordering_fields = ["metric", "threshold", "updated_at"]


class AlertEventViewSet(ServiceModelViewSet):
    serializer_class = AlertEventSerializer
    permission_classes = [RoleBasedPermission]
    service_class = AlertEventService
    allowed_roles = OBSERVABILITY_ROLES
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["metric", "severity", "rule"]
    search_fields = ["summary"]
    ordering_fields = ["created_at", "observed_value", "severity"]

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST")

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        event = self.get_object()
        if event.acknowledged_at is None:
            event.acknowledged_at = timezone.now()
            event.acknowledged_by = request.user
            event.save(update_fields=["acknowledged_at", "acknowledged_by", "updated_at"])
            record_audit_event(
                actor=request.user,
                event_type="alert.acknowledged",
                entity_type="alert_event",
                entity_id=event.id,
                severity=event.severity,
                summary=f"Alert acknowledged: {event.summary}",
                metadata={"metric": event.metric, "alert_rule_id": event.rule_id},
            )
        return Response(self.get_serializer(event).data)
