from __future__ import annotations

import csv
import hashlib
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import connection, models, transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_date
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

from apps.inventory.models import MediaSite, MediaUnit
from apps.campaigns.models import Campaign
from apps.campaigns.services import build_campaign_performance_analytics
from apps.bookings.models import Booking
from apps.billing.models import Invoice, Payment
from apps.billing.services import build_collection_efficiency_analytics
from apps.issues.models import Issue
from apps.notifications.models import EmailNotificationLog, Notification
from apps.poe.models import ProofOfExecution
from apps.poe.services import get_poe_sla_status, get_poe_sla_thresholds, resolve_review_sla_status
from apps.tenants.services import is_platform_super_admin, scope_queryset_to_tenant_path, scope_users_to_requesting_tenant
from apps.users.models import User
from core.repositories import BaseRepository
from core.roles import ADMIN, CLIENT, FIELD_STAFF, FINANCE, OPERATIONS, SALES
from core.services import BaseService

from .models import AlertEvent, AlertRule, ApiRequestLog, AuditEvent, DashboardWidgetPreference, ImportExportJob, OperationalMode, SavedOperationalView


SENSITIVE_METADATA_KEYS = {"password", "token", "otp", "authorization", "secret", "private_key", "file", "image"}
IMPORT_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}
IMPORT_MAX_BYTES = 5 * 1024 * 1024
IMPORT_PREVIEW_LIMIT = 50
INVENTORY_IMPORT_TEMPLATE_FILENAME = "OMMS_Inventory_Import_Template.xlsx"
INVENTORY_IMPORT_TEMPLATE_COLUMNS = [
    "site_code",
    "site_name",
    "site_type",
    "address",
    "city",
    "state",
    "latitude",
    "longitude",
    "unit_code",
    "width",
    "height",
    "monthly_rate",
    "status",
]
IMPORT_REQUIRED_SITE_FIELDS = {"site_code", "site_name", "site_type", "address", "city", "state"}
IMPORT_REQUIRED_UNIT_FIELDS = {"unit_code", "width", "height", "monthly_rate"}
IMPORT_SITE_FIELD_ALIASES = {
    "code": "site_code",
    "name": "site_name",
    "latitude": "site_latitude",
    "longitude": "site_longitude",
    "lat": "site_latitude",
    "lng": "site_longitude",
    "long": "site_longitude",
}
SEARCH_MODULE_LIMIT = 6
SEARCH_RESULT_LIMIT = 30
OPERATIONAL_SEARCH_MODULES = {
    "campaigns",
    "invoices",
    "clients",
    "poes",
    "jobs",
    "alerts",
    "audit",
    "notifications",
    "sites",
    "units",
}
BILLING_SEARCH_ROLES = {"admin", "finance"}
DASHBOARD_WIDGETS = {
    "operational_health": {
        "label": "Operational health",
        "category": "operations",
        "description": "System health, live jobs, request failures, and diagnostics.",
        "href": "/operations",
    },
    "critical_campaigns": {
        "label": "Critical campaigns",
        "category": "campaigns",
        "description": "Campaigns with critical delivery or commercial risk.",
        "href": "/campaigns",
    },
    "billing_risk": {
        "label": "Billing risk",
        "category": "finance",
        "description": "Overdue invoices, collection efficiency, and payment risk.",
        "href": "/billing",
    },
    "alerts": {
        "label": "Alerts",
        "category": "operations",
        "description": "Active operational alerts and threshold breaches.",
        "href": "/operations",
    },
    "campaign_performance": {
        "label": "Campaign performance",
        "category": "campaigns",
        "description": "Active campaigns, delivery health, and POE completion.",
        "href": "/campaigns",
    },
    "poe_sla": {
        "label": "POE SLA",
        "category": "poe",
        "description": "Pending reviews, breaches, suspicious proofs, and review risk.",
        "href": "/poe",
    },
    "reviewer_workload": {
        "label": "Reviewer workload",
        "category": "poe",
        "description": "Reviewer load, unassigned proofs, and review outcomes.",
        "href": "/operations",
    },
    "import_export_jobs": {
        "label": "Import/export jobs",
        "category": "operations",
        "description": "Active, failed, completed, and retryable operational jobs.",
        "href": "/operations",
    },
    "overdue_invoices": {
        "label": "Overdue invoices",
        "category": "finance",
        "description": "Overdue invoice count, value, and escalation state.",
        "href": "/billing",
    },
    "collection_efficiency": {
        "label": "Collection efficiency",
        "category": "finance",
        "description": "Collection percentage, payment trend, and pending receivables.",
        "href": "/billing",
    },
    "invoice_payment_trend": {
        "label": "Invoice/payment trend",
        "category": "finance",
        "description": "Invoice and payment trend lines for finance monitoring.",
        "href": "/billing",
    },
    "billing_alerts": {
        "label": "Billing alerts",
        "category": "finance",
        "description": "Finance-owned alerts for overdue and failed payment workflows.",
        "href": "/notifications",
    },
    "assigned_work": {
        "label": "Assigned work",
        "category": "field",
        "description": "Current field assignments and site tasks.",
        "href": "/poe/capture",
    },
    "pending_poe_uploads": {
        "label": "Pending POE uploads",
        "category": "field",
        "description": "POE captures still needed for assigned bookings.",
        "href": "/poe/capture",
    },
    "upload_status": {
        "label": "Upload status",
        "category": "field",
        "description": "Recent proof upload and verification feedback.",
        "href": "/poe/capture",
    },
    "site_task_alerts": {
        "label": "Site/task alerts",
        "category": "field",
        "description": "Task issues and assigned work alerts.",
        "href": "/notifications",
    },
    "client_campaign_status": {
        "label": "Campaign status",
        "category": "client",
        "description": "Client-visible campaign progress and status.",
        "href": "/campaigns",
    },
    "approved_poes": {
        "label": "Approved POEs",
        "category": "client",
        "description": "Approved proofs and campaign execution evidence.",
        "href": "/poe",
    },
    "client_invoices": {
        "label": "Invoices/statements",
        "category": "client",
        "description": "Client-visible invoice and statement status.",
        "href": "/billing",
    },
}
DASHBOARD_ROLE_DEFAULTS = {
    ADMIN: ["operational_health", "critical_campaigns", "billing_risk", "alerts", "campaign_performance", "poe_sla"],
    SALES: ["campaign_performance", "critical_campaigns", "client_campaign_status", "alerts"],
    OPERATIONS: ["poe_sla", "reviewer_workload", "campaign_performance", "import_export_jobs", "alerts"],
    FINANCE: ["overdue_invoices", "collection_efficiency", "invoice_payment_trend", "billing_alerts"],
    FIELD_STAFF: ["assigned_work", "pending_poe_uploads", "upload_status", "site_task_alerts"],
    CLIENT: ["client_campaign_status", "approved_poes", "client_invoices"],
}
FINANCE_WIDGETS = {"billing_risk", "overdue_invoices", "collection_efficiency", "invoice_payment_trend", "billing_alerts", "client_invoices"}
OPERATIONS_INTELLIGENCE_WIDGETS = {"operational_health", "alerts", "reviewer_workload", "import_export_jobs"}
REQUIRED_DASHBOARD_WIDGETS = {"assigned_work", "client_campaign_status"}
def get_company_name() -> str:
    try:
        from apps.setup.models import CompanyProfile

        profile = CompanyProfile.objects.filter(singleton_key=1).first()
        return profile.branding_name if profile else ""
    except Exception:
        return ""


def get_dashboard_cache_version() -> int:
    return cache.get("dashboard:version", 1)


def bump_dashboard_cache_version() -> int:
    version = cache.get("dashboard:version", 1) + 1
    cache.set("dashboard:version", version, None)
    return version


def scrub_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    scrubbed = {}
    for key, item in value.items():
        lower_key = str(key).lower()
        if any(secret in lower_key for secret in SENSITIVE_METADATA_KEYS):
            scrubbed[key] = "[redacted]"
        elif isinstance(item, dict):
            scrubbed[key] = scrub_metadata(item)
        else:
            scrubbed[key] = item
    return scrubbed


def categorize_path(path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part]
    if "auth" in parts or "token" in parts:
        return ApiRequestLog.Category.AUTH
    for category in ApiRequestLog.Category.values:
        if category != ApiRequestLog.Category.OTHER and category in parts:
            return category
    return ApiRequestLog.Category.OTHER


def get_client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def log_api_request(*, request, response, duration_ms: int, query_count: int | None = None, query_time_ms: int | None = None):
    user = getattr(request, "user", None)
    user = user if getattr(user, "is_authenticated", False) else None
    threshold = getattr(settings, "OMMS_SLOW_REQUEST_MS", 1000)
    ApiRequestLog.objects.create(
        user=user,
        company_name=get_company_name(),
        method=request.method,
        path=request.path[:500],
        status_code=getattr(response, "status_code", 0) or 0,
        duration_ms=max(0, int(duration_ms)),
        is_slow=duration_ms >= threshold,
        category=categorize_path(request.path),
        ip_address=get_client_ip(request) or None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:255],
        query_count=query_count,
        query_time_ms=query_time_ms,
    )


def record_audit_event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: str | int | None = "",
    actor=None,
    severity: str = AuditEvent.Severity.INFO,
    summary: str,
    metadata: dict[str, Any] | None = None,
    campaign_reference: str = "",
    client_reference: str = "",
    invoice_reference: str = "",
) -> AuditEvent:
    return AuditEvent.objects.create(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id or ""),
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        severity=severity,
        summary=summary[:255],
        metadata=scrub_metadata(metadata),
        campaign_reference=str(campaign_reference or "")[:120],
        client_reference=str(client_reference or "")[:120],
        invoice_reference=str(invoice_reference or "")[:120],
    )


class ApiRequestLogRepository(BaseRepository):
    model = ApiRequestLog
    select_related = ("user",)


class AuditEventRepository(BaseRepository):
    model = AuditEvent
    select_related = ("actor",)


class ImportExportJobRepository(BaseRepository):
    model = ImportExportJob
    select_related = ("created_by",)

    def scope_queryset(self, queryset, user=None):
        return queryset.filter(company_name=get_company_name())


class ApiRequestLogService(BaseService):
    repository_class = ApiRequestLogRepository


class AuditEventService(BaseService):
    repository_class = AuditEventRepository


class ImportExportJobService(BaseService):
    repository_class = ImportExportJobRepository

    def create(self, actor=None, **validated_data):
        validated_data.setdefault("created_by", actor if getattr(actor, "is_authenticated", False) else None)
        validated_data.setdefault("company_name", get_company_name())
        return super().create(actor=actor, **validated_data)


class SavedOperationalViewRepository(BaseRepository):
    model = SavedOperationalView
    select_related = ("user",)

    def scope_queryset(self, queryset, user=None):
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        return queryset.filter(user=user, company_name=get_company_name())


class SavedOperationalViewService(BaseService):
    repository_class = SavedOperationalViewRepository

    def create(self, actor=None, **validated_data):
        validated_data.setdefault("user", actor)
        validated_data.setdefault("company_name", get_company_name())
        return super().create(actor=actor, **validated_data)

    def update(self, instance, actor=None, **validated_data):
        validated_data.pop("user", None)
        validated_data.pop("company_name", None)
        return super().update(instance, actor=actor, **validated_data)


class DashboardWidgetPreferenceRepository(BaseRepository):
    model = DashboardWidgetPreference
    select_related = ("user",)

    def scope_queryset(self, queryset, user=None):
        if not user or not getattr(user, "is_authenticated", False):
            return queryset.none()
        return queryset.filter(user=user, company_name=get_company_name())


class DashboardWidgetPreferenceService(BaseService):
    repository_class = DashboardWidgetPreferenceRepository


def can_view_dashboard_finance(user) -> bool:
    role = getattr(user, "role", "")
    return bool(getattr(user, "is_superuser", False) or role in {ADMIN, FINANCE, SALES, CLIENT})


def can_view_dashboard_operations(user) -> bool:
    role = getattr(user, "role", "")
    return bool(getattr(user, "is_superuser", False) or role in {ADMIN, OPERATIONS, FINANCE})


def get_role_dashboard_defaults(role: str) -> list[str]:
    return list(DASHBOARD_ROLE_DEFAULTS.get(role, DASHBOARD_ROLE_DEFAULTS[CLIENT]))


def _is_widget_allowed_for_user(widget_key: str, user) -> bool:
    role = getattr(user, "role", "")
    if widget_key in FINANCE_WIDGETS and not can_view_dashboard_finance(user):
        return False
    if widget_key in OPERATIONS_INTELLIGENCE_WIDGETS and not can_view_dashboard_operations(user):
        return False
    if role == FIELD_STAFF and DASHBOARD_WIDGETS[widget_key]["category"] != "field":
        return False
    if role == CLIENT and DASHBOARD_WIDGETS[widget_key]["category"] not in {"client", "finance"}:
        return False
    return True


def build_dashboard_profile(user) -> dict[str, Any]:
    role = getattr(user, "role", CLIENT) or CLIENT
    company_name = get_company_name()
    default_widgets = [key for key in get_role_dashboard_defaults(role) if _is_widget_allowed_for_user(key, user)]
    preferences = {
        preference.widget_key: preference
        for preference in DashboardWidgetPreference.objects.filter(user=user, company_name=company_name)
    }
    available_widgets = []
    active_widgets = []
    hidden_widgets = []
    sorted_keys = sorted(
        [key for key in DASHBOARD_WIDGETS if _is_widget_allowed_for_user(key, user)],
        key=lambda item: (
            preferences.get(item).sort_order if item in preferences else default_widgets.index(item) if item in default_widgets else 100,
            DASHBOARD_WIDGETS[item]["label"],
        ),
    )
    for index, key in enumerate(sorted_keys):
        preference = preferences.get(key)
        is_default_visible = key in default_widgets
        is_visible = preference.is_visible if preference else is_default_visible
        if key in REQUIRED_DASHBOARD_WIDGETS:
            is_visible = True
        if is_visible:
            active_widgets.append(key)
        else:
            hidden_widgets.append(key)
        available_widgets.append(
            {
                "key": key,
                "label": DASHBOARD_WIDGETS[key]["label"],
                "category": DASHBOARD_WIDGETS[key]["category"],
                "description": DASHBOARD_WIDGETS[key]["description"],
                "href": DASHBOARD_WIDGETS[key]["href"],
                "is_visible": is_visible,
                "is_required": key in REQUIRED_DASHBOARD_WIDGETS,
                "sort_order": preference.sort_order if preference else index,
            }
        )
    return {
        "role": role,
        "role_label": role.replace("_", " ").title(),
        "active_widgets": active_widgets,
        "available_widgets": available_widgets,
        "hidden_widgets": hidden_widgets,
        "can_customize": role not in {FIELD_STAFF, CLIENT},
        "can_view_finance": can_view_dashboard_finance(user),
        "can_view_operations": can_view_dashboard_operations(user),
    }


def save_dashboard_widget_preferences(user, widgets: list[dict[str, Any]]) -> dict[str, Any]:
    if not user or not getattr(user, "is_authenticated", False):
        raise ValueError("Authenticated user is required.")
    profile = build_dashboard_profile(user)
    if not profile["can_customize"]:
        raise ValueError("Dashboard customization is not available for this role.")
    allowed_keys = {widget["key"] for widget in profile["available_widgets"]}
    company_name = get_company_name()
    with transaction.atomic():
        for index, widget in enumerate(widgets):
            widget_key = str(widget.get("widget_key") or widget.get("key") or "")
            if widget_key not in allowed_keys:
                continue
            if widget_key in REQUIRED_DASHBOARD_WIDGETS:
                is_visible = True
            else:
                is_visible = bool(widget.get("is_visible", True))
            DashboardWidgetPreference.objects.update_or_create(
                user=user,
                company_name=company_name,
                widget_key=widget_key,
                defaults={"is_visible": is_visible, "sort_order": int(widget.get("sort_order", index) or index)},
            )
    return build_dashboard_profile(user)


def reset_dashboard_widget_preferences(user) -> dict[str, Any]:
    DashboardWidgetPreference.objects.filter(user=user, company_name=get_company_name()).delete()
    return build_dashboard_profile(user)


class AlertRuleRepository(BaseRepository):
    model = AlertRule


class AlertEventRepository(BaseRepository):
    model = AlertEvent
    select_related = ("rule",)


class AlertRuleService(BaseService):
    repository_class = AlertRuleRepository


class AlertEventService(BaseService):
    repository_class = AlertEventRepository


def _split_modules(raw_modules: str | None) -> set[str]:
    if not raw_modules:
        return set(OPERATIONAL_SEARCH_MODULES)
    requested = {module.strip().lower() for module in raw_modules.split(",") if module.strip()}
    return requested & OPERATIONAL_SEARCH_MODULES


def _date_filter(queryset, field_name: str, params: dict[str, Any]):
    date_from = parse_date(str(params.get("date_from") or ""))
    date_to = parse_date(str(params.get("date_to") or ""))
    if date_from:
        queryset = queryset.filter(**{f"{field_name}__date__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field_name}__date__lte": date_to})
    return queryset


def _date_filter_date_field(queryset, field_name: str, params: dict[str, Any]):
    date_from = parse_date(str(params.get("date_from") or ""))
    date_to = parse_date(str(params.get("date_to") or ""))
    if date_from:
        queryset = queryset.filter(**{f"{field_name}__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field_name}__lte": date_to})
    return queryset


def _result(*, module: str, obj_id, title: str, subtitle: str = "", status: str = "", url: str = "", created_at=None, metadata=None):
    return {
        "module": module,
        "id": str(obj_id),
        "title": title,
        "subtitle": subtitle,
        "status": status,
        "url": url,
        "created_at": created_at,
        "metadata": metadata or {},
    }


def _append_limited(results: list[dict[str, Any]], rows):
    remaining = max(0, SEARCH_RESULT_LIMIT - len(results))
    if remaining:
        results.extend(list(rows)[:remaining])


def _can_view_billing(user) -> bool:
    return getattr(user, "role", "") in BILLING_SEARCH_ROLES or is_platform_super_admin(user)


def build_operational_search(user, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    query = str(params.get("q") or params.get("query") or "").strip()[:120]
    status_filter = str(params.get("status") or "").strip()
    modules = _split_modules(str(params.get("module") or params.get("modules") or ""))
    can_view_billing = _can_view_billing(user)
    results: list[dict[str, Any]] = []

    if not query and not status_filter and not params.get("date_from") and not params.get("date_to"):
        return {"query": query, "total": 0, "results": [], "grouped": {}}

    if "campaigns" in modules:
        queryset = scope_queryset_to_tenant_path(
            Campaign.objects.select_related("client").order_by("-updated_at"),
            user,
        )
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(client__email__icontains=query) | Q(client__organization_name__icontains=query))
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        queryset = _date_filter_date_field(queryset, "start_date", params)
        _append_limited(
            results,
            (
                _result(
                    module="campaigns",
                    obj_id=campaign.id,
                    title=campaign.name,
                    subtitle=f"{campaign.code} · {campaign.client.organization_name or campaign.client.email}",
                    status=campaign.status,
                    url="/campaigns",
                    created_at=campaign.created_at,
                    metadata={"code": campaign.code, "client": campaign.client.email},
                )
                for campaign in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if can_view_billing and "invoices" in modules:
        queryset = scope_queryset_to_tenant_path(
            Invoice.objects.select_related("campaign", "campaign__client").order_by("-created_at"),
            user,
            "campaign__tenant",
        )
        if query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=query)
                | Q(campaign__name__icontains=query)
                | Q(campaign__code__icontains=query)
                | Q(client_legal_name__icontains=query)
                | Q(campaign__client__email__icontains=query)
            )
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        queryset = _date_filter(queryset, "created_at", params)
        _append_limited(
            results,
            (
                _result(
                    module="invoices",
                    obj_id=invoice.id,
                    title=invoice.invoice_number or f"Draft invoice #{invoice.id}",
                    subtitle=f"{invoice.campaign.name} · ₹{invoice.grand_total or invoice.total_amount}",
                    status=invoice.status,
                    url=f"/billing/invoices/{invoice.id}",
                    created_at=invoice.created_at,
                    metadata={"campaign": invoice.campaign.code, "amount": str(invoice.grand_total or invoice.total_amount)},
                )
                for invoice in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if can_view_billing and "clients" in modules:
        queryset = scope_users_to_requesting_tenant(
            User.objects.filter(role=User.Role.CLIENT).order_by("organization_name", "email"),
            user,
        )
        if query:
            queryset = queryset.filter(Q(email__icontains=query) | Q(organization_name__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
        _append_limited(
            results,
            (
                _result(
                    module="clients",
                    obj_id=client.id,
                    title=client.organization_name or client.email,
                    subtitle=client.email,
                    status="client",
                    url="/campaigns",
                    created_at=client.created_at,
                    metadata={"role": client.role},
                )
                for client in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "poes" in modules:
        queryset = scope_queryset_to_tenant_path(
            ProofOfExecution.objects.select_related("booking", "booking__campaign", "booking__media_unit", "booking__media_unit__site").order_by("-captured_at"),
            user,
            "booking__campaign__tenant",
        )
        if query:
            queryset = queryset.filter(
                Q(booking__campaign__name__icontains=query)
                | Q(booking__campaign__code__icontains=query)
                | Q(booking__media_unit__unit_code__icontains=query)
                | Q(booking__media_unit__site__name__icontains=query)
                | Q(booking__media_unit__site__code__icontains=query)
            )
        if status_filter:
            queryset = queryset.filter(verification_status=status_filter)
        queryset = _date_filter(queryset, "captured_at", params)
        _append_limited(
            results,
            (
                _result(
                    module="poes",
                    obj_id=poe.id,
                    title=f"POE #{poe.id} · {poe.booking.campaign.name}",
                    subtitle=f"{poe.booking.media_unit.site.name} · {poe.booking.media_unit.unit_code}",
                    status=poe.verification_status,
                    url="/poe",
                    created_at=poe.captured_at,
                    metadata={"campaign": poe.booking.campaign.code, "booking_id": poe.booking_id},
                )
                for poe in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "jobs" in modules:
        queryset = ImportExportJob.objects.filter(company_name=get_company_name()).select_related("created_by").order_by("-created_at")
        if query:
            queryset = queryset.filter(Q(resource_type__icontains=query) | Q(job_type__icontains=query) | Q(created_by__email__icontains=query))
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        queryset = _date_filter(queryset, "created_at", params)
        _append_limited(
            results,
            (
                _result(
                    module="jobs",
                    obj_id=job.id,
                    title=f"{job.get_job_type_display()} · {job.get_resource_type_display()}",
                    subtitle=f"{job.rows_success} success · {job.rows_failed} failed",
                    status=job.status,
                    url="/operations",
                    created_at=job.created_at,
                    metadata={"job_type": job.job_type, "resource_type": job.resource_type},
                )
                for job in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "alerts" in modules:
        queryset = AlertEvent.objects.select_related("rule").order_by("-created_at")
        if query:
            queryset = queryset.filter(Q(summary__icontains=query) | Q(metric__icontains=query) | Q(rule__name__icontains=query))
        if status_filter:
            if status_filter == "acknowledged":
                queryset = queryset.filter(acknowledged_at__isnull=False)
            elif status_filter == "open":
                queryset = queryset.filter(acknowledged_at__isnull=True)
            else:
                queryset = queryset.filter(severity=status_filter)
        queryset = _date_filter(queryset, "created_at", params)
        _append_limited(
            results,
            (
                _result(
                    module="alerts",
                    obj_id=alert.id,
                    title=alert.summary,
                    subtitle=alert.rule.name,
                    status="acknowledged" if alert.acknowledged_at else alert.severity,
                    url="/operations",
                    created_at=alert.created_at,
                    metadata={"metric": alert.metric, "observed_value": alert.observed_value},
                )
                for alert in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "audit" in modules:
        queryset = AuditEvent.objects.select_related("actor").filter(company_name=get_company_name()).order_by("-created_at")
        if query:
            queryset = queryset.filter(Q(summary__icontains=query) | Q(event_type__icontains=query) | Q(entity_type__icontains=query) | Q(campaign_reference__icontains=query) | Q(client_reference__icontains=query))
        if status_filter:
            queryset = queryset.filter(severity=status_filter)
        queryset = _date_filter(queryset, "created_at", params)
        _append_limited(
            results,
            (
                _result(
                    module="audit",
                    obj_id=event.id,
                    title=event.summary,
                    subtitle=f"{event.event_type} · {event.actor.email if event.actor else 'system'}",
                    status=event.severity,
                    url="/operations",
                    created_at=event.created_at,
                    metadata={"entity_type": event.entity_type, "entity_id": event.entity_id},
                )
                for event in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "notifications" in modules:
        queryset = Notification.objects.filter(Q(recipient=user) | Q(recipient_role=getattr(user, "role", "")), company_name=get_company_name()).order_by("-created_at")
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(message__icontains=query) | Q(event_type__icontains=query))
        if status_filter:
            queryset = queryset.filter(Q(severity=status_filter) | Q(event_type=status_filter))
        queryset = _date_filter(queryset, "created_at", params)
        _append_limited(
            results,
            (
                _result(
                    module="notifications",
                    obj_id=notification.id,
                    title=notification.title,
                    subtitle=notification.message[:120],
                    status=notification.severity,
                    url="/notifications",
                    created_at=notification.created_at,
                    metadata={"event_type": notification.event_type, "is_read": notification.is_read},
                )
                for notification in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "sites" in modules:
        queryset = scope_queryset_to_tenant_path(MediaSite.objects.order_by("name"), user)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(city__icontains=query) | Q(address__icontains=query))
        if status_filter:
            queryset = queryset.filter(location_status=status_filter)
        _append_limited(
            results,
            (
                _result(
                    module="sites",
                    obj_id=site.id,
                    title=site.name,
                    subtitle=f"{site.code} · {site.city}, {site.state}",
                    status=site.location_status,
                    url="/inventory",
                    created_at=site.created_at,
                    metadata={"code": site.code, "site_type": site.site_type},
                )
                for site in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    if "units" in modules:
        queryset = scope_queryset_to_tenant_path(MediaUnit.objects.select_related("site").order_by("unit_code"), user, "site__tenant")
        if query:
            queryset = queryset.filter(Q(unit_code__icontains=query) | Q(site__name__icontains=query) | Q(site__code__icontains=query))
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        _append_limited(
            results,
            (
                _result(
                    module="units",
                    obj_id=unit.id,
                    title=unit.unit_code,
                    subtitle=f"{unit.site.name} · {unit.width}x{unit.height}",
                    status=unit.status,
                    url="/inventory",
                    created_at=unit.created_at,
                    metadata={"site_code": unit.site.code, "monthly_rate": str(unit.monthly_rate)},
                )
                for unit in queryset[:SEARCH_MODULE_LIMIT]
            ),
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results[:SEARCH_RESULT_LIMIT]:
        grouped.setdefault(item["module"], []).append(item)
    return {"query": query, "total": len(results[:SEARCH_RESULT_LIMIT]), "results": results[:SEARCH_RESULT_LIMIT], "grouped": grouped}


def cleanup_old_request_logs(*, days: int | None = None) -> int:
    retention_days = days or getattr(settings, "OMMS_REQUEST_LOG_RETENTION_DAYS", 30)
    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = ApiRequestLog.objects.filter(created_at__lt=cutoff).delete()
    return deleted_count


def refresh_invoice_status_job() -> int:
    from apps.billing.models import Invoice
    from apps.billing.services import refresh_invoice_payment_statuses

    return refresh_invoice_payment_statuses(
        queryset=Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
    )


def notification_retry_job(limit: int = 50) -> int:
    from apps.notifications.services import NotificationService

    return NotificationService().mark_due_retries_pending(limit=limit)


def get_deployment_environment_metadata() -> dict[str, Any]:
    database_engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    return {
        "environment_name": getattr(settings, "OMMS_ENVIRONMENT_NAME", ""),
        "debug": bool(getattr(settings, "DEBUG", False)),
        "frontend_url": getattr(settings, "FRONTEND_PUBLIC_BASE_URL", ""),
        "backend_url": getattr(settings, "OMMS_BACKEND_PUBLIC_BASE_URL", ""),
        "redis_configured": bool(getattr(settings, "CELERY_BROKER_URL", "")),
        "celery_eager": bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)),
        "database_engine": database_engine.rsplit(".", 1)[-1] if database_engine else "",
        "app_version": getattr(settings, "OMMS_APP_VERSION", ""),
        "git_commit": getattr(settings, "OMMS_GIT_COMMIT", ""),
    }


def get_operational_mode() -> OperationalMode:
    mode, _ = OperationalMode.objects.get_or_create(singleton_key=1)
    return mode


def update_operational_mode(*, mode: str, message: str = "", actor=None) -> OperationalMode:
    if mode not in OperationalMode.Mode.values:
        raise ValueError("Unsupported operational mode.")
    operational_mode = get_operational_mode()
    operational_mode.mode = mode
    operational_mode.message = message.strip()[:255]
    operational_mode.updated_by = actor if actor and getattr(actor, "is_authenticated", False) else None
    operational_mode.save(update_fields=["mode", "message", "updated_by", "updated_at"])
    record_audit_event(
        event_type="environment.mode_updated",
        entity_type="operational_mode",
        entity_id=str(operational_mode.pk),
        actor=actor,
        severity=AuditEvent.Severity.WARNING if mode != OperationalMode.Mode.NORMAL else AuditEvent.Severity.INFO,
        summary=f"Environment mode changed to {operational_mode.get_mode_display()}.",
        metadata={"mode": mode, "message": operational_mode.message},
    )
    return operational_mode


def build_operational_mode_payload() -> dict[str, Any]:
    mode = get_operational_mode()
    return {
        "mode": mode.mode,
        "label": mode.get_mode_display(),
        "message": mode.message,
        "is_write_blocking": mode.mode in {OperationalMode.Mode.MAINTENANCE, OperationalMode.Mode.READ_ONLY},
        "updated_at": mode.updated_at,
        "updated_by_email": mode.updated_by.email if mode.updated_by else None,
    }


def build_system_health_diagnostics(*, now=None) -> dict[str, Any]:
    now = now or timezone.now()
    since = now - timedelta(hours=24)
    database_ok = True
    diagnostic_query_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database_ok = False

    celery_enabled = bool(getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True))
    celery_eager = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))
    broker_configured = bool(getattr(settings, "CELERY_BROKER_URL", ""))
    beat_configured = bool(getattr(settings, "CELERY_BEAT_SCHEDULE", {}))
    active_job_statuses = [ImportExportJob.Status.CONFIRMED, ImportExportJob.Status.PROCESSING, ImportExportJob.Status.RUNNING]
    try:
        operational_mode = get_operational_mode()
    except Exception:
        operational_mode = None
    if database_ok:
        try:
            recent_failed_requests = ApiRequestLog.objects.filter(status_code__gte=500, created_at__gte=since).count()
            recent_slow_requests = ApiRequestLog.objects.filter(is_slow=True, created_at__gte=since).count()
            recent_failed_jobs = ImportExportJob.objects.filter(status=ImportExportJob.Status.FAILED, updated_at__gte=since).count()
            latest_successful_import = ImportExportJob.objects.filter(
                job_type=ImportExportJob.JobType.IMPORT,
                status=ImportExportJob.Status.COMPLETED,
            ).order_by("-completed_at", "-updated_at").first()
            latest_successful_export = ImportExportJob.objects.filter(
                job_type=ImportExportJob.JobType.EXPORT,
                status=ImportExportJob.Status.COMPLETED,
            ).order_by("-completed_at", "-updated_at").first()
            active_jobs = ImportExportJob.objects.filter(status__in=active_job_statuses).count()
        except Exception:
            diagnostic_query_ok = False
            recent_failed_requests = 0
            recent_slow_requests = 0
            recent_failed_jobs = 0
            latest_successful_import = None
            latest_successful_export = None
            active_jobs = 0
    else:
        recent_failed_requests = 0
        recent_slow_requests = 0
        recent_failed_jobs = 0
        latest_successful_import = None
        latest_successful_export = None
        active_jobs = 0

    signals = []
    if not database_ok:
        signals.append("database_unavailable")
    if not diagnostic_query_ok:
        signals.append("diagnostic_queries_unavailable")
    if celery_enabled and not broker_configured:
        signals.append("broker_not_configured")
    if recent_failed_requests >= 10:
        signals.append("failed_request_spike")
    if recent_failed_jobs >= 2:
        signals.append("failed_background_jobs")
    if recent_slow_requests >= 25:
        signals.append("slow_request_spike")
    if operational_mode and operational_mode.mode != OperationalMode.Mode.NORMAL:
        signals.append(f"environment_{operational_mode.mode}")

    if operational_mode and operational_mode.mode == OperationalMode.Mode.MAINTENANCE:
        status_value = "degraded"
    elif not database_ok or not diagnostic_query_ok or recent_failed_requests >= 25 or recent_failed_jobs >= 5:
        status_value = "degraded"
    elif signals:
        status_value = "warning"
    else:
        status_value = "healthy"

    return {
        "status": status_value,
        "api_status": "healthy" if recent_failed_requests < 10 and database_ok else "degraded",
        "database": {"ok": database_ok, "diagnostic_queries_ok": diagnostic_query_ok},
        "redis": {"configured": broker_configured},
        "celery": {
            "enabled": celery_enabled,
            "broker_configured": broker_configured,
            "eager": celery_eager,
            "mode": "eager" if celery_eager else "enabled" if celery_enabled else "disabled",
            "worker_ready": "unknown" if celery_enabled and not celery_eager else "not_required",
            "beat_configured": beat_configured,
        },
        "recent_failed_requests": recent_failed_requests,
        "recent_slow_requests": recent_slow_requests,
        "recent_failed_background_jobs": recent_failed_jobs,
        "active_jobs": active_jobs,
        "last_successful_import": latest_successful_import.completed_at if latest_successful_import else None,
        "last_successful_export": latest_successful_export.completed_at if latest_successful_export else None,
        "signals": signals,
        "deployment": get_deployment_environment_metadata(),
        "environment_mode": build_operational_mode_payload()
        if operational_mode
        else {
            "mode": "unknown",
            "label": "Unknown",
            "message": "",
            "is_write_blocking": False,
            "updated_at": None,
            "updated_by_email": None,
        },
    }


def ensure_default_alert_rules() -> None:
    defaults = [
        ("Slow API requests in last 24h", AlertRule.Metric.SLOW_REQUESTS, 25, 1440, AlertRule.Severity.WARNING),
        ("Failed API requests in last 24h", AlertRule.Metric.FAILED_API_REQUESTS, 10, 1440, AlertRule.Severity.WARNING),
        ("Failed notifications in last hour", AlertRule.Metric.FAILED_NOTIFICATIONS, 3, 60, AlertRule.Severity.WARNING),
        ("Failed import/export jobs in last 24h", AlertRule.Metric.FAILED_IMPORT_EXPORT_JOBS, 2, 1440, AlertRule.Severity.WARNING),
        ("Suspicious POEs today", AlertRule.Metric.SUSPICIOUS_POES, 5, 1440, AlertRule.Severity.WARNING),
        ("Overdue POE reviews", AlertRule.Metric.OVERDUE_POE_REVIEWS, 5, 1440, AlertRule.Severity.WARNING),
        ("POE SLA breaches", AlertRule.Metric.POE_SLA_BREACHES, 1, 1440, AlertRule.Severity.CRITICAL),
        ("Critical campaign risk", AlertRule.Metric.CAMPAIGNS_AT_RISK, 1, 1440, AlertRule.Severity.CRITICAL),
        ("System health degraded", AlertRule.Metric.SYSTEM_HEALTH_DEGRADED, 1, 15, AlertRule.Severity.CRITICAL),
        ("Breached issues", AlertRule.Metric.BREACHED_ISSUES, 1, 1440, AlertRule.Severity.CRITICAL),
        ("Overdue invoices", AlertRule.Metric.OVERDUE_INVOICES, 5, 1440, AlertRule.Severity.WARNING),
    ]
    for name, metric, threshold, window_minutes, severity in defaults:
        AlertRule.objects.get_or_create(
            metric=metric,
            defaults={
                "name": name,
                "threshold": threshold,
                "window_minutes": window_minutes,
                "severity": severity,
            },
        )


def get_alert_metric_value(rule: AlertRule, *, now=None) -> int:
    now = now or timezone.now()
    since = now - timedelta(minutes=rule.window_minutes)
    if rule.metric == AlertRule.Metric.SLOW_REQUESTS:
        return ApiRequestLog.objects.filter(is_slow=True, created_at__gte=since).count()
    if rule.metric == AlertRule.Metric.FAILED_API_REQUESTS:
        return ApiRequestLog.objects.filter(status_code__gte=500, created_at__gte=since).count()
    if rule.metric == AlertRule.Metric.FAILED_NOTIFICATIONS:
        return EmailNotificationLog.objects.filter(status=EmailNotificationLog.Status.FAILED, updated_at__gte=since).count()
    if rule.metric == AlertRule.Metric.FAILED_IMPORT_EXPORT_JOBS:
        return ImportExportJob.objects.filter(status=ImportExportJob.Status.FAILED, updated_at__gte=since).count()
    if rule.metric == AlertRule.Metric.SUSPICIOUS_POES:
        return ProofOfExecution.objects.filter(
            verification_status__in=[ProofOfExecution.VerificationStatus.SUSPICIOUS, ProofOfExecution.VerificationStatus.REJECTED],
            created_at__gte=since,
        ).count()
    if rule.metric == AlertRule.Metric.OVERDUE_POE_REVIEWS:
        return ProofOfExecution.objects.filter(reviewed_at__isnull=True, review_due_at__lt=now).count()
    if rule.metric == AlertRule.Metric.POE_SLA_BREACHES:
        return build_poe_sla_intelligence(now=now)["breach_count"]
    if rule.metric == AlertRule.Metric.CAMPAIGNS_AT_RISK:
        return build_campaign_performance_analytics()["critical_count"]
    if rule.metric == AlertRule.Metric.SYSTEM_HEALTH_DEGRADED:
        return 1 if build_system_health_diagnostics(now=now)["status"] == "degraded" else 0
    if rule.metric == AlertRule.Metric.BREACHED_ISSUES:
        return Issue.objects.filter(sla_status=Issue.SlaStatus.BREACHED).exclude(status=Issue.Status.RESOLVED).count()
    if rule.metric == AlertRule.Metric.OVERDUE_INVOICES:
        return build_collection_efficiency_analytics()["overdue_invoice_count"]
    return 0


def evaluate_alert_thresholds(*, now=None) -> list[AlertEvent]:
    ensure_default_alert_rules()
    now = now or timezone.now()
    created_events = []
    for rule in AlertRule.objects.filter(is_enabled=True):
        observed_value = get_alert_metric_value(rule, now=now)
        if observed_value < rule.threshold:
            continue
        cooldown_since = now - timedelta(minutes=rule.cooldown_minutes)
        if AlertEvent.objects.filter(rule=rule, created_at__gte=cooldown_since).exists():
            continue
        summary = f"{rule.name}: observed {observed_value}, threshold {rule.threshold}."
        event = AlertEvent.objects.create(
            rule=rule,
            metric=rule.metric,
            observed_value=observed_value,
            threshold=rule.threshold,
            severity=rule.severity,
            summary=summary,
            metadata={"window_minutes": rule.window_minutes},
        )
        record_audit_event(
            event_type="alert.triggered",
            entity_type="alert_rule",
            entity_id=rule.id,
            severity=rule.severity,
            summary=summary,
            metadata={"metric": rule.metric, "observed_value": observed_value, "threshold": rule.threshold},
        )
        try:
            from apps.notifications.services import NotificationService

            NotificationService().notify_operations(
                event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
                title=f"Operational alert: {rule.name}",
                message=summary,
                severity="critical" if rule.severity == AlertRule.Severity.CRITICAL else "warning",
                metadata={"alert_rule_id": rule.id, "alert_event_id": event.id},
            )
            if rule.metric == AlertRule.Metric.OVERDUE_INVOICES:
                for role in ("admin", "finance"):
                    NotificationService().create_internal_notification(
                        recipient_role=role,
                        event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
                        title=f"Billing risk alert: {rule.name}",
                        message=summary,
                        severity="critical" if rule.severity == AlertRule.Severity.CRITICAL else "warning",
                        metadata={"alert_rule_id": rule.id, "alert_event_id": event.id, "metric": rule.metric},
                    )
            if rule.metric == AlertRule.Metric.CAMPAIGNS_AT_RISK:
                for role in ("admin", "operations"):
                    NotificationService().create_internal_notification(
                        recipient_role=role,
                        event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
                        title=f"Campaign risk alert: {rule.name}",
                        message=summary,
                        severity="critical" if rule.severity == AlertRule.Severity.CRITICAL else "warning",
                        metadata={"alert_rule_id": rule.id, "alert_event_id": event.id, "metric": rule.metric},
                    )
            if rule.metric == AlertRule.Metric.SYSTEM_HEALTH_DEGRADED:
                for role in ("admin", "operations"):
                    NotificationService().create_internal_notification(
                        recipient_role=role,
                        event_type=EmailNotificationLog.NotificationType.SYSTEM_DIAGNOSTIC_ALERT,
                        title=f"System health alert: {rule.name}",
                        message=summary,
                        severity="critical",
                        metadata={"alert_rule_id": rule.id, "alert_event_id": event.id, "metric": rule.metric},
                    )
        except Exception:
            pass
        created_events.append(event)
    return created_events


def build_poe_analytics(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    queryset = scope_queryset_to_tenant_path(
        ProofOfExecution.objects.select_related(
            "booking",
            "booking__campaign",
            "booking__media_unit",
            "booking__media_unit__site",
            "checked_by",
        ),
        filters.get("_user"),
        "booking__campaign__tenant",
    )
    if filters.get("campaign"):
        queryset = queryset.filter(booking__campaign_id=filters["campaign"])
    if filters.get("site"):
        queryset = queryset.filter(booking__media_unit__site_id=filters["site"])
    if filters.get("field_agent"):
        queryset = queryset.filter(media_items__captured_by_id=filters["field_agent"]).distinct()
    if filters.get("status"):
        queryset = queryset.filter(verification_status=filters["status"])
    if filters.get("date_from"):
        queryset = queryset.filter(captured_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(captured_at__date__lte=filters["date_to"])

    now = timezone.now()
    records = list(queryset[:1000])
    pending_review = [record for record in records if not record.reviewed_at]
    missing_gps = [record for record in records if record.latitude is None or record.longitude is None]
    suspicious = [
        record
        for record in records
        if record.verification_status in {ProofOfExecution.VerificationStatus.SUSPICIOUS, ProofOfExecution.VerificationStatus.REJECTED}
    ]
    overdue = [record for record in pending_review if record.review_due_at and record.review_due_at < now]
    outside_geofence = [
        record
        for record in records
        if record.verification_logs.filter(distance_meters__gt=models.F("threshold_meters")).exists()
    ]
    duplicate_bookings = (
        queryset.values("booking_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .count()
    )
    trend_rows = (
        queryset.extra(select={"day": "date(captured_at)"})
        .values("day")
        .annotate(total=Count("id"), suspicious=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)))
        .order_by("day")
    )
    return {
        "total_poes": len(records),
        "suspicious_count": len(suspicious),
        "outside_geofence_count": len(outside_geofence),
        "missing_gps_count": len(missing_gps),
        "duplicate_replacement_count": duplicate_bookings,
        "pending_review_count": len(pending_review),
        "overdue_review_count": len(overdue),
        "trends_by_date": list(trend_rows),
        "recent_suspicious": [
            {
                "id": record.id,
                "campaign": record.booking.campaign.name,
                "site": record.booking.media_unit.site.name,
                "status": record.verification_status,
                "review_sla_status": resolve_review_sla_status(record),
                "captured_at": record.captured_at,
            }
            for record in suspicious[:10]
        ],
    }


def build_poe_sla_intelligence(filters: dict[str, Any] | None = None, *, now=None) -> dict[str, Any]:
    filters = filters or {}
    now = now or timezone.now()
    thresholds = get_poe_sla_thresholds()
    queryset = scope_queryset_to_tenant_path(
        ProofOfExecution.objects.select_related("checked_by", "booking__campaign").all(),
        filters.get("_user"),
        "booking__campaign__tenant",
    )
    if filters.get("date_from"):
        queryset = queryset.filter(captured_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(captured_at__date__lte=filters["date_to"])

    warning_count = 0
    breach_count = 0
    suspicious_unresolved_count = 0
    unassigned_count = 0
    oldest_pending = None
    pending_by_reviewer: dict[str, dict[str, Any]] = {}

    for record in queryset:
        sla = get_poe_sla_status(record, now=now)
        if sla["status"] == "warning":
            warning_count += 1
        elif sla["status"] == "breached":
            breach_count += 1
        if sla["is_suspicious_unresolved"]:
            suspicious_unresolved_count += 1
        if record.verification_status == ProofOfExecution.VerificationStatus.PENDING and not record.reviewed_at:
            if record.checked_by_id is None:
                unassigned_count += 1
            if oldest_pending is None or record.captured_at < oldest_pending.captured_at:
                oldest_pending = record
            key = record.checked_by.email if record.checked_by else "Unassigned"
            bucket = pending_by_reviewer.setdefault(key, {"reviewer": key, "pending": 0})
            bucket["pending"] += 1

    reviewer_activity = list(
        queryset.values("checked_by__email")
        .annotate(
            approved=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.VERIFIED)),
            rejected=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.REJECTED)),
            suspicious=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)),
        )
        .order_by("checked_by__email")
    )
    reviewer_rows = []
    for row in reviewer_activity:
        reviewer = row["checked_by__email"] or "Unassigned"
        pending = pending_by_reviewer.get(reviewer, {}).get("pending", 0)
        reviewer_rows.append(
            {
                "reviewer": reviewer,
                "pending": pending,
                "approved": row["approved"],
                "rejected": row["rejected"],
                "rework": row["suspicious"],
                "is_overloaded": pending >= thresholds["reviewer_overload_threshold"],
            }
        )
    for reviewer, pending_row in pending_by_reviewer.items():
        if not any(row["reviewer"] == reviewer for row in reviewer_rows):
            reviewer_rows.append(
                {
                    "reviewer": reviewer,
                    "pending": pending_row["pending"],
                    "approved": 0,
                    "rejected": 0,
                    "rework": 0,
                    "is_overloaded": pending_row["pending"] >= thresholds["reviewer_overload_threshold"],
                }
            )
    reviewer_rows = sorted(reviewer_rows, key=lambda row: row["pending"], reverse=True)[:10]

    return {
        "warning_count": warning_count,
        "breach_count": breach_count,
        "oldest_pending": {
            "id": oldest_pending.id,
            "captured_at": oldest_pending.captured_at,
            "campaign": oldest_pending.booking.campaign.name,
            "age_hours": get_poe_sla_status(oldest_pending, now=now)["age_hours"],
        }
        if oldest_pending
        else None,
        "unassigned_count": unassigned_count,
        "reviewer_workload": reviewer_rows,
        "suspicious_unresolved_count": suspicious_unresolved_count,
        "thresholds": thresholds,
    }


def _apply_created_range(queryset, filters: dict[str, Any]):
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])
    return queryset


def _daily_counts(queryset, *, date_field: str = "created_at", value_name: str = "total", extra_annotations: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    annotations = {"day": TruncDate(date_field)}
    values = queryset.annotate(**annotations).values("day")
    aggregate_kwargs = {value_name: Count("id")}
    if extra_annotations:
        aggregate_kwargs.update(extra_annotations)
    return list(values.annotate(**aggregate_kwargs).order_by("day"))


def _company_filter(queryset, filters: dict[str, Any]):
    company = filters.get("company") or filters.get("tenant")
    if company and hasattr(queryset.model, "company_name"):
        return queryset.filter(company_name__icontains=company)
    return queryset


def _site_region_label(city: str | None, state: str | None) -> str:
    city = (city or "").strip()
    state = (state or "").strip()
    if city and state:
        return f"{city}, {state}"
    return city or state or "Unknown region"


def build_operational_heatmap_intelligence(filters: dict[str, Any] | None = None, *, now=None) -> dict[str, Any]:
    """Build capped region/site activity aggregates without exposing raw coordinates."""
    filters = filters or {}
    now = now or timezone.now()
    default_since = now - timedelta(days=30)

    poe_queryset = ProofOfExecution.objects.select_related(
        "checked_by",
        "booking__campaign",
        "booking__media_unit__site",
    ).all()
    booking_queryset = Booking.objects.select_related("campaign", "media_unit__site").exclude(status=Booking.Status.CANCELLED)
    poe_queryset = scope_queryset_to_tenant_path(poe_queryset, filters.get("_user"), "booking__campaign__tenant")
    booking_queryset = scope_queryset_to_tenant_path(booking_queryset, filters.get("_user"), "campaign__tenant")
    job_queryset = _company_filter(ImportExportJob.objects.all(), filters)
    alert_queryset = AlertEvent.objects.select_related("rule").all()

    if filters.get("date_from"):
        poe_queryset = poe_queryset.filter(captured_at__date__gte=filters["date_from"])
        booking_queryset = booking_queryset.filter(created_at__date__gte=filters["date_from"])
        job_queryset = job_queryset.filter(created_at__date__gte=filters["date_from"])
        alert_queryset = alert_queryset.filter(created_at__date__gte=filters["date_from"])
    else:
        poe_queryset = poe_queryset.filter(captured_at__gte=default_since)
        booking_queryset = booking_queryset.filter(created_at__gte=default_since)
        job_queryset = job_queryset.filter(created_at__gte=default_since)
        alert_queryset = alert_queryset.filter(created_at__gte=default_since)
    if filters.get("date_to"):
        poe_queryset = poe_queryset.filter(captured_at__date__lte=filters["date_to"])
        booking_queryset = booking_queryset.filter(created_at__date__lte=filters["date_to"])
        job_queryset = job_queryset.filter(created_at__date__lte=filters["date_to"])
        alert_queryset = alert_queryset.filter(created_at__date__lte=filters["date_to"])
    if filters.get("campaign"):
        poe_queryset = poe_queryset.filter(
            Q(booking__campaign__name__icontains=filters["campaign"]) | Q(booking__campaign__code__icontains=filters["campaign"])
        )
        booking_queryset = booking_queryset.filter(
            Q(campaign__name__icontains=filters["campaign"]) | Q(campaign__code__icontains=filters["campaign"])
        )
    if filters.get("reviewer"):
        poe_queryset = poe_queryset.filter(checked_by__email__icontains=filters["reviewer"])
    if filters.get("city"):
        poe_queryset = poe_queryset.filter(booking__media_unit__site__city__icontains=filters["city"])
        booking_queryset = booking_queryset.filter(media_unit__site__city__icontains=filters["city"])
    if filters.get("state"):
        poe_queryset = poe_queryset.filter(booking__media_unit__site__state__icontains=filters["state"])
        booking_queryset = booking_queryset.filter(media_unit__site__state__icontains=filters["state"])
    if str(filters.get("suspicious_only", "")).lower() in {"1", "true", "yes"}:
        poe_queryset = poe_queryset.filter(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)
    if filters.get("severity"):
        alert_queryset = alert_queryset.filter(severity=filters["severity"])
    activity_type = (filters.get("activity_type") or "").strip().lower()
    if activity_type in {"suspicious", "suspicious_poe", "suspicious_activity"}:
        poe_queryset = poe_queryset.filter(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)
    elif activity_type in {"delayed", "delayed_poe", "poe_delay"}:
        poe_queryset = poe_queryset.filter(review_sla_status=ProofOfExecution.ReviewSlaStatus.OVERDUE)
    elif activity_type in {"campaign", "campaigns", "campaign_density"}:
        job_queryset = job_queryset.none()
        alert_queryset = alert_queryset.none()
    elif activity_type in {"jobs", "imports", "exports"}:
        poe_queryset = poe_queryset.none()
        booking_queryset = booking_queryset.none()
        alert_queryset = alert_queryset.none()
    elif activity_type == "alerts":
        poe_queryset = poe_queryset.none()
        booking_queryset = booking_queryset.none()
        job_queryset = job_queryset.none()

    region_rows = list(
        poe_queryset.values("booking__media_unit__site__city", "booking__media_unit__site__state")
        .annotate(
            total_uploads=Count("id"),
            suspicious_count=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)),
            delayed_count=Count("id", filter=Q(review_sla_status=ProofOfExecution.ReviewSlaStatus.OVERDUE)),
            pending_count=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.PENDING)),
        )
        .order_by("-total_uploads", "-suspicious_count")[:8]
    )
    region_activity = [
        {
            "region": _site_region_label(row["booking__media_unit__site__city"], row["booking__media_unit__site__state"]),
            "city": row["booking__media_unit__site__city"] or "",
            "state": row["booking__media_unit__site__state"] or "",
            "total_uploads": row["total_uploads"],
            "suspicious_count": row["suspicious_count"],
            "delayed_count": row["delayed_count"],
            "pending_count": row["pending_count"],
            "intensity": min(100, row["total_uploads"] * 12 + row["suspicious_count"] * 18 + row["delayed_count"] * 18),
        }
        for row in region_rows
    ]

    site_rows = list(
        poe_queryset.values(
            "booking__media_unit__site__id",
            "booking__media_unit__site__name",
            "booking__media_unit__site__code",
            "booking__media_unit__site__city",
            "booking__media_unit__site__state",
        )
        .annotate(
            total_uploads=Count("id"),
            suspicious_count=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)),
            delayed_count=Count("id", filter=Q(review_sla_status=ProofOfExecution.ReviewSlaStatus.OVERDUE)),
        )
        .order_by("-suspicious_count", "-delayed_count", "-total_uploads")[:10]
    )
    site_activity = [
        {
            "site_id": row["booking__media_unit__site__id"],
            "site_name": row["booking__media_unit__site__name"] or "Unknown site",
            "site_code": row["booking__media_unit__site__code"] or "",
            "region": _site_region_label(row["booking__media_unit__site__city"], row["booking__media_unit__site__state"]),
            "total_uploads": row["total_uploads"],
            "suspicious_count": row["suspicious_count"],
            "delayed_count": row["delayed_count"],
        }
        for row in site_rows
    ]

    campaign_density = list(
        booking_queryset.values("media_unit__site__city", "media_unit__site__state")
        .annotate(campaigns=Count("campaign", distinct=True), booked_sites=Count("media_unit__site", distinct=True))
        .order_by("-campaigns", "-booked_sites")[:8]
    )
    campaign_regions = [
        {
            "region": _site_region_label(row["media_unit__site__city"], row["media_unit__site__state"]),
            "campaigns": row["campaigns"],
            "booked_sites": row["booked_sites"],
        }
        for row in campaign_density
    ]

    reviewer_rows = list(
        poe_queryset.values("checked_by__email")
        .annotate(
            reviewed=Count("id", filter=Q(reviewed_at__isnull=False)),
            pending=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.PENDING)),
            suspicious=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)),
        )
        .order_by("-pending", "-reviewed")[:8]
    )
    reviewer_load = [
        {
            "reviewer": row["checked_by__email"] or "Unassigned",
            "reviewed": row["reviewed"],
            "pending": row["pending"],
            "suspicious": row["suspicious"],
        }
        for row in reviewer_rows
    ]

    upload_trend = list(
        poe_queryset.annotate(day=TruncDate("captured_at"))
        .values("day")
        .annotate(
            uploads=Count("id"),
            suspicious=Count("id", filter=Q(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS)),
            delayed=Count("id", filter=Q(review_sla_status=ProofOfExecution.ReviewSlaStatus.OVERDUE)),
        )
        .order_by("day")[:31]
    )
    operational_activity = {
        "poe_uploads": poe_queryset.count(),
        "suspicious_poes": poe_queryset.filter(verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS).count(),
        "delayed_reviews": poe_queryset.filter(review_sla_status=ProofOfExecution.ReviewSlaStatus.OVERDUE).count(),
        "campaign_bookings": booking_queryset.count(),
        "alerts": alert_queryset.count(),
        "jobs": job_queryset.count(),
    }
    top_busy = region_activity[0] if region_activity else None
    top_suspicious = max(region_activity, key=lambda row: row["suspicious_count"], default=None)
    top_delayed = max(region_activity, key=lambda row: row["delayed_count"], default=None)
    hotspot_flag = bool(top_suspicious and top_suspicious["suspicious_count"] >= 3)

    return {
        "summary": {
            "total_activity": sum(operational_activity.values()),
            "busy_regions": len(region_activity),
            "suspicious_regions": sum(1 for row in region_activity if row["suspicious_count"] > 0),
            "delayed_regions": sum(1 for row in region_activity if row["delayed_count"] > 0),
            "hotspot_flag": hotspot_flag,
            "plain_language": "Review suspicious activity areas first." if hotspot_flag else "No major activity hotspot detected.",
        },
        "top_busy_region": top_busy,
        "top_suspicious_region": top_suspicious if top_suspicious and top_suspicious["suspicious_count"] else None,
        "top_delayed_region": top_delayed if top_delayed and top_delayed["delayed_count"] else None,
        "region_activity": region_activity,
        "site_activity": site_activity,
        "campaign_regions": campaign_regions,
        "reviewer_load": reviewer_load,
        "upload_trend": upload_trend,
        "operational_activity": operational_activity,
        "alert_density": list(alert_queryset.values("metric", "severity").annotate(total=Count("id")).order_by("-total")[:8]),
        "job_density": list(job_queryset.values("job_type", "resource_type", "status").annotate(total=Count("id")).order_by("-total")[:8]),
        "filters_applied": {
            "date_from": filters.get("date_from") or default_since.date().isoformat(),
            "date_to": filters.get("date_to") or "",
            "activity_type": filters.get("activity_type") or "all",
            "suspicious_only": str(filters.get("suspicious_only", "")).lower() in {"1", "true", "yes"},
            "city": filters.get("city") or "",
            "state": filters.get("state") or "",
        },
    }


def _risk_level(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _confidence_from_factors(factors: list[dict[str, Any]]) -> int:
    if not factors:
        return 55
    return min(95, 58 + len(factors) * 9)


def _recommendation(identifier: str, title: str, action: str, severity: str, factors: list[str]) -> dict[str, Any]:
    return {
        "id": identifier,
        "title": title,
        "recommended_action": action,
        "severity": severity,
        "confidence": _confidence_from_factors([{"label": factor} for factor in factors]),
        "why": factors,
        "is_automatic": False,
    }


def build_predictive_operations_intelligence(
    *,
    poe_sla: dict[str, Any] | None = None,
    campaign_performance: dict[str, Any] | None = None,
    billing_intelligence: dict[str, Any] | None = None,
    operational_heatmap: dict[str, Any] | None = None,
    kpis: dict[str, Any] | None = None,
    can_view_finance: bool = True,
) -> dict[str, Any]:
    """Deterministic, explainable prediction layer. No autonomous actions are produced."""
    poe_sla = poe_sla or {}
    campaign_performance = campaign_performance or {}
    billing_intelligence = billing_intelligence or {}
    operational_heatmap = operational_heatmap or {}
    kpis = kpis or {}
    recommendations: list[dict[str, Any]] = []

    campaign_risks = []
    for campaign in (campaign_performance.get("campaigns") or [])[:8]:
        factors: list[dict[str, Any]] = []
        score = 10
        pending = int(campaign.get("pending_poe_count") or 0)
        suspicious = int(campaign.get("suspicious_poe_count") or 0)
        is_ending_soon = bool(campaign.get("is_ending_soon"))
        overdue_amount = Decimal(str(campaign.get("overdue_amount") or "0"))
        delay_count = len(campaign.get("operational_delay_indicators") or [])
        if pending:
            score += min(30, pending * 6)
            factors.append({"label": f"{pending} pending POE(s)", "impact": min(30, pending * 6)})
        if suspicious:
            score += min(28, suspicious * 10)
            factors.append({"label": f"{suspicious} suspicious POE(s)", "impact": min(28, suspicious * 10)})
        if is_ending_soon:
            score += 18
            factors.append({"label": "Campaign ending soon", "impact": 18})
        if can_view_finance and overdue_amount > 0:
            score += 22
            factors.append({"label": "Overdue invoice exposure", "impact": 22})
        if delay_count:
            score += min(15, delay_count * 5)
            factors.append({"label": f"{delay_count} operational delay signal(s)", "impact": min(15, delay_count * 5)})
        score = min(100, score)
        level = _risk_level(score)
        row = {
            "campaign_id": campaign.get("campaign_id"),
            "campaign_code": campaign.get("campaign_code", ""),
            "campaign_name": campaign.get("campaign_name", "Unknown campaign"),
            "risk_score": score,
            "risk_level": level,
            "confidence": _confidence_from_factors(factors),
            "contributing_factors": factors,
        }
        campaign_risks.append(row)
        if level in {"high", "critical"}:
            recommendations.append(
                _recommendation(
                    f"campaign-{campaign.get('campaign_id')}",
                    f"Prioritize {row['campaign_name']}",
                    "Review pending POEs, suspicious proofs, and commercial blockers before campaign close.",
                    "critical" if level == "critical" else "warning",
                    [factor["label"] for factor in factors],
                )
            )
    campaign_risks = sorted(campaign_risks, key=lambda row: row["risk_score"], reverse=True)

    reviewer_predictions = []
    overload_threshold = int((poe_sla.get("thresholds") or {}).get("reviewer_overload_threshold") or 10)
    for reviewer in poe_sla.get("reviewer_workload") or []:
        pending = int(reviewer.get("pending") or 0)
        throughput = int(reviewer.get("approved") or 0) + int(reviewer.get("rejected") or 0)
        rework = int(reviewer.get("rework") or 0)
        projected_pending = pending + max(0, rework // 2) - max(0, throughput // 6)
        projected_pending = max(0, projected_pending)
        factors = []
        if pending >= overload_threshold:
            factors.append("Current queue is already at overload threshold")
        elif projected_pending >= overload_threshold:
            factors.append("Projected queue may cross overload threshold")
        if rework:
            factors.append(f"{rework} suspicious/rework outcome(s) add review pressure")
        if throughput == 0 and pending:
            factors.append("No recent completed review outcomes in the current view")
        severity = "critical" if projected_pending >= overload_threshold else "warning" if projected_pending >= max(1, overload_threshold - 2) else "normal"
        reviewer_predictions.append(
            {
                "reviewer": reviewer.get("reviewer", "Unassigned"),
                "current_pending": pending,
                "projected_pending": projected_pending,
                "overload_threshold": overload_threshold,
                "severity": severity,
                "confidence": _confidence_from_factors([{"label": item} for item in factors]),
                "suggested_signal": "Redistribute reviews" if severity in {"critical", "warning"} else "No redistribution needed",
                "contributing_factors": factors,
            }
        )
    for row in reviewer_predictions:
        if row["severity"] in {"critical", "warning"}:
            recommendations.append(
                _recommendation(
                    f"reviewer-{row['reviewer']}",
                    f"Balance reviewer load for {row['reviewer']}",
                    row["suggested_signal"],
                    row["severity"],
                    row["contributing_factors"] or [f"{row['current_pending']} pending review(s)"],
                )
            )

    suspicious_patterns = []
    top_suspicious = operational_heatmap.get("top_suspicious_region")
    if top_suspicious:
        suspicious_patterns.append(
            {
                "type": "Suspicious activity area",
                "label": top_suspicious.get("region", "Unknown region"),
                "count": top_suspicious.get("suspicious_count", 0),
                "confidence": 76,
                "why": [
                    f"{top_suspicious.get('suspicious_count', 0)} suspicious proof(s)",
                    f"{top_suspicious.get('total_uploads', 0)} recent upload(s)",
                ],
            }
        )
    for site in (operational_heatmap.get("site_activity") or [])[:5]:
        if int(site.get("suspicious_count") or 0) >= 2:
            suspicious_patterns.append(
                {
                    "type": "Repeated suspicious site activity",
                    "label": site.get("site_name", "Unknown site"),
                    "count": site.get("suspicious_count", 0),
                    "confidence": 80,
                    "why": [f"{site.get('suspicious_count')} suspicious proof(s) at this site"],
                }
            )

    collection_risks = []
    if can_view_finance:
        for client in billing_intelligence.get("top_overdue_clients") or []:
            amount = Decimal(str(client.get("amount") or "0"))
            oldest = int(client.get("oldest_days_overdue") or 0)
            score = min(100, 25 + min(35, oldest) + min(30, int(amount // Decimal("50000")) * 8) + int(client.get("count") or 0) * 5)
            level = _risk_level(score)
            factors = [f"{client.get('count', 0)} overdue invoice(s)", f"Oldest overdue is {oldest} day(s)"]
            if amount > 0:
                factors.append(f"Overdue value {amount}")
            collection_risks.append(
                {
                    "client": client.get("client", "Unknown client"),
                    "risk_score": score,
                    "risk_level": level,
                    "confidence": _confidence_from_factors([{"label": item} for item in factors]),
                    "recommended_escalation": "Owner follow-up" if level in {"high", "critical"} else "Finance follow-up",
                    "contributing_factors": factors,
                }
            )
    if collection_risks:
        top_collection = collection_risks[0]
        recommendations.append(
            _recommendation(
                f"collection-{top_collection['client']}",
                f"Follow up {top_collection['client']}",
                top_collection["recommended_escalation"],
                "critical" if top_collection["risk_level"] == "critical" else "warning",
                top_collection["contributing_factors"],
            )
        )

    bottlenecks = []
    if int(poe_sla.get("breach_count") or 0):
        bottlenecks.append({"area": "Delayed POE reviews", "severity": "critical", "count": poe_sla.get("breach_count"), "why": "POE SLA breaches are active"})
    if int((operational_heatmap.get("summary") or {}).get("delayed_regions") or 0):
        bottlenecks.append({"area": "Delayed areas", "severity": "warning", "count": operational_heatmap["summary"]["delayed_regions"], "why": "One or more regions have delayed POE reviews"})
    if int(kpis.get("failed_jobs") or 0):
        bottlenecks.append({"area": "Background jobs", "severity": "warning", "count": kpis.get("failed_jobs"), "why": "Failed import/export jobs need operator review"})

    upload_trend = operational_heatmap.get("upload_trend") or []
    average_uploads = round(sum(int(row.get("uploads") or 0) for row in upload_trend[-7:]) / max(1, len(upload_trend[-7:])))
    average_suspicious = round(sum(int(row.get("suspicious") or 0) for row in upload_trend[-7:]) / max(1, len(upload_trend[-7:])))
    forecasts = {
        "next_3_days": [
            {
                "label": f"Day {index}",
                "expected_poe_load": average_uploads,
                "expected_suspicious": average_suspicious,
                "reviewer_pressure": "high" if any(row["severity"] in {"critical", "warning"} for row in reviewer_predictions) else "normal",
                "confidence": 65 if upload_trend else 45,
            }
            for index in range(1, 4)
        ],
        "explanation": "Forecast uses recent average upload and suspicious activity counts; it is directional, not an autonomous decision.",
    }

    if top_suspicious:
        recommendations.append(
            _recommendation(
                "suspicious-region",
                f"Investigate {top_suspicious.get('region', 'suspicious region')}",
                "Review suspicious proofs and field context for this area.",
                "warning",
                [f"{top_suspicious.get('suspicious_count', 0)} suspicious proof(s)", "Regional hotspot detected"],
            )
        )

    urgency = max(
        [row["risk_score"] for row in campaign_risks[:1]] + [85 if any(row["severity"] == "critical" for row in reviewer_predictions) else 0] + [70 if bottlenecks else 0]
    )
    priority_widgets = ["poe_sla", "campaign_performance", "alerts", "operational_health"]
    if can_view_finance and collection_risks and collection_risks[0]["risk_score"] >= 65:
        priority_widgets = ["billing_risk", "collection_efficiency", *priority_widgets]

    return {
        "summary": {
            "highest_risk_level": _risk_level(urgency),
            "highest_risk_score": urgency,
            "confidence": 78 if recommendations else 55,
            "plain_language": recommendations[0]["title"] if recommendations else "No major predictive risk detected.",
            "guardrail": "Recommendations only. No automatic approvals, campaign changes, or financial modifications.",
        },
        "campaign_risks": campaign_risks[:8],
        "reviewer_load_predictions": reviewer_predictions[:8],
        "suspicious_patterns": suspicious_patterns[:8],
        "collection_risks": collection_risks[:5],
        "bottlenecks": bottlenecks[:6],
        "recommendations": recommendations[:8],
        "forecasts": forecasts,
        "priority_widgets": priority_widgets[:6],
        "explainability": {
            "method": "Deterministic rule-assisted scoring from current OMMS operational aggregates.",
            "not_used_for": ["automatic POE approval", "financial modification", "campaign closure", "destructive actions"],
        },
    }
def build_empty_operations_summary(*, error: str = "") -> dict[str, Any]:
    system_health = {
        "status": "degraded" if error else "unknown",
        "api_status": "degraded" if error else "unknown",
        "database": {"ok": False if error else True},
        "redis": {"configured": bool(getattr(settings, "CELERY_BROKER_URL", ""))},
        "celery": {
            "enabled": bool(getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True)),
            "broker_configured": bool(getattr(settings, "CELERY_BROKER_URL", "")),
            "eager": bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)),
            "mode": "unknown",
            "worker_ready": "unknown",
            "beat_configured": bool(getattr(settings, "CELERY_BEAT_SCHEDULE", {})),
        },
        "recent_failed_requests": 0,
        "recent_slow_requests": 0,
        "recent_failed_background_jobs": 0,
        "signals": ["summary_unavailable"] if error else [],
        "deployment": get_deployment_environment_metadata(),
        "celery_mode": "unknown",
        "broker_configured": bool(getattr(settings, "CELERY_BROKER_URL", "")),
        "active_jobs": 0,
        "failed_jobs": 0,
        "api_failure_count": 0,
        "api_failure_percentage": 0,
        "last_successful_import": None,
        "last_successful_export": None,
        "notification_retries_due": 0,
    }
    return {
        "poe": {
            "total_poes": 0,
            "suspicious_count": 0,
            "outside_geofence_count": 0,
            "missing_gps_count": 0,
            "duplicate_replacement_count": 0,
            "pending_review_count": 0,
            "overdue_review_count": 0,
            "trends_by_date": [],
            "recent_suspicious": [],
        },
        "kpis": {
            "active_jobs": 0,
            "failed_jobs": 0,
            "suspicious_poes": 0,
            "pending_poe_reviews": 0,
            "poe_sla_warnings": 0,
            "poe_sla_breaches": 0,
            "notifications_today": 0,
            "failed_requests": 0,
            "active_users_today": 0,
            "campaigns_running": 0,
            "campaigns_ending_soon": 0,
            "campaigns_poe_risk": 0,
            "campaigns_billing_risk": 0,
            "critical_campaigns": 0,
            "invoice_collection_rate": 0,
            "overdue_invoices": 0,
            "overdue_invoice_value": Decimal("0.00"),
            "export_activity_today": 0,
        },
        "billing_intelligence": {
            "total_invoiced_amount": Decimal("0.00"),
            "collected_amount": Decimal("0.00"),
            "pending_amount": Decimal("0.00"),
            "overdue_amount": Decimal("0.00"),
            "overdue_invoice_count": 0,
            "collection_efficiency_percentage": 0,
            "average_days_to_payment": None,
            "overdue_age_buckets": [],
            "top_overdue_clients": [],
            "payment_trend": [],
        },
        "campaign_performance": {
            "active_campaigns": 0,
            "ending_soon_count": 0,
            "poe_risk_count": 0,
            "billing_risk_count": 0,
            "at_risk_count": 0,
            "critical_count": 0,
            "can_view_billing": False,
            "risk_distribution": [],
            "poe_completion_trend": [],
            "operational_health_trend": [],
            "campaigns": [],
        },
        "poe_sla": {
            "warning_count": 0,
            "breach_count": 0,
            "oldest_pending": None,
            "unassigned_count": 0,
            "reviewer_workload": [],
            "suspicious_unresolved_count": 0,
            "thresholds": get_poe_sla_thresholds(),
        },
        "operational_heatmap": {
            "summary": {
                "total_activity": 0,
                "busy_regions": 0,
                "suspicious_regions": 0,
                "delayed_regions": 0,
                "hotspot_flag": False,
                "plain_language": "No operational activity available.",
            },
            "top_busy_region": None,
            "top_suspicious_region": None,
            "top_delayed_region": None,
            "region_activity": [],
            "site_activity": [],
            "campaign_regions": [],
            "reviewer_load": [],
            "upload_trend": [],
            "operational_activity": {
                "poe_uploads": 0,
                "suspicious_poes": 0,
                "delayed_reviews": 0,
                "campaign_bookings": 0,
                "alerts": 0,
                "jobs": 0,
            },
            "alert_density": [],
            "job_density": [],
            "filters_applied": {},
        },
        "predictive_operations": {
            "summary": {
                "highest_risk_level": "low",
                "highest_risk_score": 0,
                "confidence": 55,
                "plain_language": "No major predictive risk detected.",
                "guardrail": "Recommendations only. No automatic approvals, campaign changes, or financial modifications.",
            },
            "campaign_risks": [],
            "reviewer_load_predictions": [],
            "suspicious_patterns": [],
            "collection_risks": [],
            "bottlenecks": [],
            "recommendations": [],
            "forecasts": {"next_3_days": [], "explanation": ""},
            "priority_widgets": [],
            "explainability": {
                "method": "Deterministic rule-assisted scoring from current OMMS operational aggregates.",
                "not_used_for": ["automatic POE approval", "financial modification", "campaign closure", "destructive actions"],
            },
        },
        "slow_requests_count": 0,
        "audit_by_severity": [],
        "notification_failures_count": 0,
        "notification_retries_due": 0,
        "recent_critical_alerts": [],
        "charts": {
            "job_activity": [],
            "request_activity": [],
            "poe_status": [],
            "reviewer_workload": [],
            "poe_reviewer_workload": [],
            "billing_activity": [],
            "payment_activity": [],
            "operations_activity": [],
            "notification_activity": [],
            "load_distribution": [],
            "campaign_risk_distribution": [],
            "campaign_poe_completion_trend": [],
            "campaign_operational_health_trend": [],
        },
        "timeline": [],
        "system_health": system_health,
        "warnings": [error] if error else [],
    }


def build_operations_summary(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    user = filters.get("_user")
    can_view_finance = bool(
        is_platform_super_admin(user)
        or getattr(user, "role", None) in {"admin", "finance"}
        or user is None
    )
    poe_payload = build_poe_analytics(filters)
    poe_sla = build_poe_sla_intelligence(filters)
    operational_heatmap = build_operational_heatmap_intelligence(filters)
    campaign_performance = build_campaign_performance_analytics(user=user)
    request_queryset = _company_filter(ApiRequestLog.objects.all(), filters)
    audit_queryset = _company_filter(AuditEvent.objects.all(), filters)
    notification_queryset = EmailNotificationLog.objects.all()
    inbox_queryset = _company_filter(Notification.objects.all(), filters)
    job_queryset = _company_filter(ImportExportJob.objects.all(), filters)
    alert_queryset = AlertEvent.objects.select_related("rule")
    request_queryset = _apply_created_range(request_queryset, filters)
    audit_queryset = _apply_created_range(audit_queryset, filters)
    notification_queryset = _apply_created_range(notification_queryset, filters)
    inbox_queryset = _apply_created_range(inbox_queryset, filters)
    job_queryset = _apply_created_range(job_queryset, filters)
    alert_queryset = _apply_created_range(alert_queryset, filters)
    if filters.get("severity"):
        audit_queryset = audit_queryset.filter(severity=filters["severity"])
        inbox_queryset = inbox_queryset.filter(severity=filters["severity"])
        alert_queryset = alert_queryset.filter(severity=filters["severity"])
    if filters.get("event_type"):
        audit_queryset = audit_queryset.filter(event_type=filters["event_type"])
    if filters.get("module"):
        request_queryset = request_queryset.filter(category=filters["module"])
        audit_queryset = audit_queryset.filter(entity_type__icontains=filters["module"])
    if filters.get("status"):
        job_queryset = job_queryset.filter(status=filters["status"])
    if filters.get("role"):
        audit_queryset = audit_queryset.filter(actor__role=filters["role"])
        inbox_queryset = inbox_queryset.filter(Q(recipient__role=filters["role"]) | Q(recipient_role=filters["role"]))
    if filters.get("notification_type"):
        notification_queryset = notification_queryset.filter(notification_type=filters["notification_type"])
        inbox_queryset = inbox_queryset.filter(event_type=filters["notification_type"])

    now = timezone.now()
    today = timezone.localdate()
    campaign_queryset = scope_queryset_to_tenant_path(Campaign.objects.all(), user)
    campaigns_running = campaign_queryset.filter(status=Campaign.Status.ACTIVE, start_date__lte=today, end_date__gte=today).count()
    invoice_queryset = scope_queryset_to_tenant_path(
        Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]),
        user,
        "campaign__tenant",
    )
    billing_intelligence = build_collection_efficiency_analytics(invoice_queryset) if can_view_finance else {
        "total_invoiced_amount": Decimal("0.00"),
        "collected_amount": Decimal("0.00"),
        "pending_amount": Decimal("0.00"),
        "overdue_amount": Decimal("0.00"),
        "overdue_invoice_count": 0,
        "collection_efficiency_percentage": 0,
        "average_days_to_payment": None,
        "overdue_age_buckets": [],
        "top_overdue_clients": [],
        "payment_trend": [],
    }
    invoice_collection_rate = billing_intelligence["collection_efficiency_percentage"] if can_view_finance else 0
    active_job_statuses = [ImportExportJob.Status.CONFIRMED, ImportExportJob.Status.PROCESSING, ImportExportJob.Status.RUNNING, ImportExportJob.Status.PENDING]
    failed_request_count = request_queryset.filter(status_code__gte=500).count()
    total_request_count = request_queryset.count()
    active_users_today = scope_users_to_requesting_tenant(User.objects.filter(last_login__date=today), user).count()
    export_activity_today = job_queryset.filter(job_type=ImportExportJob.JobType.EXPORT, created_at__date=today).count()
    latest_successful_import = job_queryset.filter(job_type=ImportExportJob.JobType.IMPORT, status=ImportExportJob.Status.COMPLETED).order_by("-completed_at", "-updated_at").first()
    latest_successful_export = job_queryset.filter(job_type=ImportExportJob.JobType.EXPORT, status=ImportExportJob.Status.COMPLETED).order_by("-completed_at", "-updated_at").first()

    job_activity = (
        job_queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            imports=Count("id", filter=Q(job_type=ImportExportJob.JobType.IMPORT)),
            exports=Count("id", filter=Q(job_type=ImportExportJob.JobType.EXPORT)),
            failed=Count("id", filter=Q(status=ImportExportJob.Status.FAILED)),
        )
        .order_by("day")
    )
    request_activity = (
        request_queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Count("id"),
            failed=Count("id", filter=Q(status_code__gte=500)),
            slow=Count("id", filter=Q(is_slow=True)),
        )
        .order_by("day")
    )
    poe_queryset = scope_queryset_to_tenant_path(ProofOfExecution.objects.all(), user, "booking__campaign__tenant")
    if filters.get("date_from"):
        poe_queryset = poe_queryset.filter(captured_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        poe_queryset = poe_queryset.filter(captured_at__date__lte=filters["date_to"])
    poe_status = list(poe_queryset.values("verification_status").annotate(total=Count("id")).order_by("verification_status"))
    reviewer_workload = list(
        poe_queryset.values("checked_by__email").annotate(total=Count("id")).order_by("-total")[:8]
    )
    billing_activity = (
        invoice_queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            invoices=Count("id"),
            paid=Count("id", filter=Q(status=Invoice.Status.PAID)),
            overdue=Count("id", filter=Q(status=Invoice.Status.OVERDUE)),
        )
        .order_by("day")
    ) if can_view_finance else []
    payment_queryset = scope_queryset_to_tenant_path(Payment.objects.all(), user, "invoice__campaign__tenant")
    payment_activity = _daily_counts(payment_queryset, date_field="payment_date", value_name="payments") if can_view_finance else []
    operations_activity = (
        audit_queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(events=Count("id"))
        .order_by("day")
    )
    notification_activity = _daily_counts(inbox_queryset, value_name="notifications")
    load_distribution = list(audit_queryset.values("entity_type").annotate(total=Count("id")).order_by("-total")[:8])
    audit_timeline = [
        {
            "id": f"audit-{event.id}",
            "kind": "audit",
            "module": event.entity_type,
            "status": event.severity,
            "summary": event.summary,
            "actor": event.actor.email if event.actor else "System",
            "created_at": event.created_at,
        }
        for event in audit_queryset.select_related("actor").order_by("-created_at")[:12]
    ]
    job_timeline = [
        {
            "id": f"job-{job.id}",
            "kind": job.job_type,
            "module": job.resource_type,
            "status": job.status,
            "summary": f"{job.job_type.title()} {job.resource_type.replace('_', ' ')} {job.status}",
            "actor": job.created_by.email if job.created_by else "System",
            "created_at": job.created_at,
        }
        for job in job_queryset.select_related("created_by").order_by("-created_at")[:8]
    ]
    poe_timeline = [
        {
            "id": f"poe-{record.id}",
            "kind": "poe",
            "module": "poe",
            "status": record.verification_status,
            "summary": f"{record.verification_status.title()} POE for {record.booking.campaign.name}",
            "actor": record.checked_by.email if record.checked_by else "System",
            "created_at": record.captured_at,
        }
        for record in poe_queryset.select_related("booking__campaign", "checked_by").filter(
            verification_status__in=[ProofOfExecution.VerificationStatus.SUSPICIOUS, ProofOfExecution.VerificationStatus.REJECTED, ProofOfExecution.VerificationStatus.VERIFIED]
        ).order_by("-captured_at")[:8]
    ]
    timeline = sorted([*audit_timeline, *job_timeline, *poe_timeline], key=lambda item: item["created_at"], reverse=True)[:20]

    kpis = {
            "active_jobs": job_queryset.filter(status__in=active_job_statuses).count(),
            "failed_jobs": job_queryset.filter(status=ImportExportJob.Status.FAILED).count(),
            "suspicious_poes": poe_payload["suspicious_count"],
            "pending_poe_reviews": poe_payload["pending_review_count"],
            "poe_sla_warnings": poe_sla["warning_count"],
            "poe_sla_breaches": poe_sla["breach_count"],
            "notifications_today": inbox_queryset.filter(created_at__date=today).count(),
            "failed_requests": failed_request_count,
            "active_users_today": active_users_today,
            "campaigns_running": campaigns_running,
            "campaigns_ending_soon": campaign_performance["ending_soon_count"],
            "campaigns_poe_risk": campaign_performance["poe_risk_count"],
            "campaigns_billing_risk": campaign_performance["billing_risk_count"],
            "critical_campaigns": campaign_performance["critical_count"],
            "invoice_collection_rate": invoice_collection_rate,
            "overdue_invoices": billing_intelligence["overdue_invoice_count"],
            "overdue_invoice_value": billing_intelligence["overdue_amount"],
            "export_activity_today": export_activity_today,
        }
    predictive_operations = build_predictive_operations_intelligence(
        poe_sla=poe_sla,
        campaign_performance=campaign_performance,
        billing_intelligence=billing_intelligence,
        operational_heatmap=operational_heatmap,
        kpis=kpis,
        can_view_finance=can_view_finance,
    )

    return {
        "poe": poe_payload,
        "kpis": kpis,
        "slow_requests_count": request_queryset.filter(is_slow=True).count(),
        "audit_by_severity": list(audit_queryset.values("severity").annotate(total=Count("id")).order_by("severity")),
        "notification_failures_count": notification_queryset.filter(status=EmailNotificationLog.Status.FAILED).count(),
        "notification_retries_due": notification_queryset.filter(
            status=EmailNotificationLog.Status.FAILED,
            next_retry_at__lte=timezone.now(),
        ).count(),
        "recent_critical_alerts": list(
            alert_queryset.filter(severity__in=[AlertRule.Severity.CRITICAL, AlertRule.Severity.WARNING])
            .values("id", "metric", "summary", "severity", "created_at", "acknowledged_at", "acknowledged_by__email")[:10]
        ),
        "charts": {
            "job_activity": list(job_activity),
            "request_activity": [
                {
                    **row,
                    "failed_percentage": round((row["failed"] / row["total"]) * 100) if row["total"] else 0,
                }
                for row in request_activity
            ],
            "poe_status": poe_status,
            "reviewer_workload": [{"reviewer": row["checked_by__email"] or "Unassigned", "total": row["total"]} for row in reviewer_workload],
            "poe_reviewer_workload": poe_sla["reviewer_workload"],
            "billing_activity": list(billing_activity),
            "payment_activity": payment_activity,
            "operations_activity": list(operations_activity),
            "notification_activity": notification_activity,
            "load_distribution": load_distribution,
            "campaign_risk_distribution": campaign_performance["risk_distribution"],
            "campaign_poe_completion_trend": campaign_performance["poe_completion_trend"],
            "campaign_operational_health_trend": campaign_performance["operational_health_trend"],
        },
        "poe_sla": poe_sla,
        "operational_heatmap": operational_heatmap,
        "predictive_operations": predictive_operations,
        "campaign_performance": campaign_performance,
        "billing_intelligence": billing_intelligence,
        "timeline": timeline,
        "system_health": {
            **build_system_health_diagnostics(now=now),
            "celery_mode": "enabled" if getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True) else "disabled",
            "broker_configured": bool(getattr(settings, "CELERY_BROKER_URL", "")),
            "active_jobs": job_queryset.filter(status__in=active_job_statuses).count(),
            "failed_jobs": job_queryset.filter(status=ImportExportJob.Status.FAILED).count(),
            "api_failure_count": failed_request_count,
            "api_failure_percentage": round((failed_request_count / total_request_count) * 100) if total_request_count else 0,
            "last_successful_import": latest_successful_import.completed_at if latest_successful_import else None,
            "last_successful_export": latest_successful_export.completed_at if latest_successful_export else None,
            "notification_retries_due": notification_queryset.filter(status=EmailNotificationLog.Status.FAILED, next_retry_at__lte=now).count(),
        },
    }


def build_role_activity(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    user = filters.get("_user")
    queryset = AuditEvent.objects.select_related("actor")
    if user is not None and not is_platform_super_admin(user):
        queryset = queryset.filter(actor__tenant=getattr(user, "tenant", None))
    if filters.get("role"):
        queryset = queryset.filter(actor__role=filters["role"])
    if filters.get("user"):
        queryset = queryset.filter(actor_id=filters["user"])
    if filters.get("event_type"):
        queryset = queryset.filter(event_type=filters["event_type"])
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])

    by_role = queryset.values("actor__role").annotate(total=Count("id")).order_by("actor__role")
    by_event = queryset.values("event_type").annotate(total=Count("id")).order_by("-total")[:20]
    return {
        "total_events": queryset.count(),
        "by_role": [{"role": row["actor__role"] or "system", "total": row["total"]} for row in by_role],
        "by_event_type": list(by_event),
    }


def build_diagnostics_payload() -> dict[str, Any]:
    system_health = build_system_health_diagnostics()
    try:
        cache_ok = cache.set("omms:diagnostics:ping", "ok", 10) and cache.get("omms:diagnostics:ping") == "ok"
    except Exception:
        cache_ok = False
    database_ok = bool(system_health.get("database", {}).get("ok")) and bool(
        system_health.get("database", {}).get("diagnostic_queries_ok", True)
    )
    return {
        "app_version": getattr(settings, "OMMS_APP_VERSION", ""),
        "git_commit": getattr(settings, "OMMS_GIT_COMMIT", ""),
        "environment": system_health["deployment"],
        "system_health": system_health,
        "database": system_health["database"],
        "cache": {"ok": bool(cache_ok), "timeout_seconds": getattr(settings, "OMMS_DASHBOARD_CACHE_SECONDS", 60)},
        "background_jobs": {
            "celery_broker_configured": system_health["celery"]["broker_configured"],
            "background_jobs_enabled": getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True),
            "mode": system_health["celery"]["mode"],
            "worker_ready": system_health["celery"]["worker_ready"],
            "beat_configured": system_health["celery"]["beat_configured"],
        },
        "request_logging": {
            "enabled": getattr(settings, "OMMS_API_REQUEST_LOGGING_ENABLED", True),
            "slow_threshold_ms": getattr(settings, "OMMS_SLOW_REQUEST_MS", 1000),
            "retention_days": getattr(settings, "OMMS_REQUEST_LOG_RETENTION_DAYS", 30),
        },
        "recent_slow_requests": list(
            ApiRequestLog.objects.filter(is_slow=True)
            .values("created_at", "method", "path", "status_code", "duration_ms", "category")[:10]
        )
        if database_ok
        else [],
        "recent_errors": list(
            ApiRequestLog.objects.filter(status_code__gte=500)
            .values("created_at", "method", "path", "status_code", "duration_ms", "category")[:10]
        )
        if database_ok
        else [],
        "recent_critical_alerts": list(
            AlertEvent.objects.filter(severity=AlertRule.Severity.CRITICAL)
            .values("created_at", "metric", "summary", "observed_value", "threshold")[:10]
        )
        if database_ok
        else [],
        "notification_retry_health": {
            "failed_count": EmailNotificationLog.objects.filter(status=EmailNotificationLog.Status.FAILED).count()
            if database_ok
            else 0,
            "due_retry_count": EmailNotificationLog.objects.filter(
                status=EmailNotificationLog.Status.FAILED,
                next_retry_at__lte=timezone.now(),
            ).count()
            if database_ok
            else 0,
        },
    }


def _normalise_import_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalise_inventory_row(row: dict[str, Any]) -> dict[str, str]:
    normalised: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        next_key = _normalise_import_key(str(key))
        next_key = IMPORT_SITE_FIELD_ALIASES.get(next_key, next_key)
        normalised[next_key] = "" if value is None else str(value).strip()
    return normalised


def build_inventory_import_template() -> tuple[str, bytes]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventory Import"
    sheet.append(INVENTORY_IMPORT_TEMPLATE_COLUMNS)
    sheet.append(
        [
            "SITE-001",
            "MG Road Billboard",
            MediaSite.SiteType.BILLBOARD,
            "MG Road near Metro Gate 2",
            "Gurugram",
            "Haryana",
            "",
            "",
            "UNIT-001-A",
            "20",
            "10",
            "50000",
            MediaUnit.Status.AVAILABLE,
        ]
    )
    sheet.append(
        [
            "SITE-002",
            "Airport Road Digital Screen",
            MediaSite.SiteType.DIGITAL,
            "Airport Road Junction",
            "Bengaluru",
            "Karnataka",
            "12.971599",
            "77.594566",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    sheet.freeze_panes = "A2"
    for cell in sheet[1]:
        cell.style = "Headline 4"

    widths = {
        "A": 16,
        "B": 28,
        "C": 20,
        "D": 34,
        "E": 18,
        "F": 18,
        "G": 14,
        "H": 14,
        "I": 18,
        "J": 12,
        "K": 12,
        "L": 16,
        "M": 16,
    }
    for column, width in widths.items():
        sheet.column_dimensions[column].width = width

    site_types = ",".join(choice[0] for choice in MediaSite.SiteType.choices)
    statuses = ",".join(choice[0] for choice in MediaUnit.Status.choices)
    site_type_validation = DataValidation(type="list", formula1=f'"{site_types}"', allow_blank=False)
    status_validation = DataValidation(type="list", formula1=f'"{statuses}"', allow_blank=True)
    sheet.add_data_validation(site_type_validation)
    sheet.add_data_validation(status_validation)
    site_type_validation.add("C2:C500")
    status_validation.add("M2:M500")

    instructions = workbook.create_sheet("Instructions")
    instruction_rows = [
        ("Purpose", "Use this template to stage inventory imports from Operations -> Import / Export Data."),
        ("No immediate import", "Uploading this file creates a validation preview first. Records are not committed until Start Import is confirmed."),
        ("Required site fields", "site_code, site_name, site_type, address, city, state."),
        ("Optional fields", "latitude, longitude, unit_code, width, height, monthly_rate, status."),
        ("Coordinates", "Latitude and longitude are optional because OMMS can capture GPS from the first verified POE."),
        ("Site type values", site_types),
        ("Status values", statuses),
        ("Duplicate handling", "Existing sites are updated safely; existing media units are skipped; repeated unit codes in the file are rejected."),
    ]
    instructions.append(("Topic", "Instruction"))
    for row in instruction_rows:
        instructions.append(row)
    instructions.column_dimensions["A"].width = 24
    instructions.column_dimensions["B"].width = 110
    for cell in instructions[1]:
        cell.style = "Headline 4"

    output = BytesIO()
    workbook.save(output)
    return INVENTORY_IMPORT_TEMPLATE_FILENAME, output.getvalue()


def _read_inventory_import_rows(file_obj) -> tuple[list[dict[str, str]], bytes, str]:
    filename = getattr(file_obj, "name", "inventory-import.csv") or "inventory-import.csv"
    lower_filename = filename.lower()
    if not any(lower_filename.endswith(extension) for extension in IMPORT_ALLOWED_EXTENSIONS):
        raise ValueError("Only CSV and Excel files are supported for inventory imports.")
    raw = file_obj.read()
    if len(raw) > getattr(settings, "OMMS_IMPORT_MAX_BYTES", IMPORT_MAX_BYTES):
        raise ValueError("Import file is too large. Upload a file under 5 MB.")

    if lower_filename.endswith(".csv"):
        text = raw.decode("utf-8-sig")
        rows = [_normalise_inventory_row(row) for row in csv.DictReader(StringIO(text))]
        return rows, raw, filename

    workbook = load_workbook(filename=ContentFile(raw), read_only=True, data_only=True)
    sheet = workbook.active
    rows_iter = sheet.iter_rows(values_only=True)
    headers = next(rows_iter, None)
    if not headers:
        return [], raw, filename
    keys = [_normalise_import_key(str(header or "")) for header in headers]
    rows = []
    for values in rows_iter:
        rows.append(_normalise_inventory_row(dict(zip(keys, values))))
    return rows, raw, filename


def _parse_decimal(value: str, *, field: str, row_number: int, errors: list[dict[str, Any]], required: bool = False):
    if value == "":
        if required:
            errors.append({"row": row_number, "error": f"{field} is required."})
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        errors.append({"row": row_number, "error": f"{field} must be a valid number."})
        return None
    if parsed < 0:
        errors.append({"row": row_number, "error": f"{field} cannot be negative."})
    return parsed


def _parse_int(value: str, *, field: str, row_number: int, errors: list[dict[str, Any]], default: int = 1):
    if value == "":
        return default
    try:
        parsed = int(Decimal(value))
    except (InvalidOperation, ValueError):
        errors.append({"row": row_number, "error": f"{field} must be a whole number."})
        return default
    if parsed <= 0:
        errors.append({"row": row_number, "error": f"{field} must be greater than zero."})
    return parsed


def _validate_inventory_row(
    row: dict[str, str],
    *,
    row_number: int,
    seen_unit_codes: set[str],
    seen_site_codes: set[str],
    seen_row_fingerprints: set[str],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    site_code = row.get("site_code", "")
    unit_code = row.get("unit_code", "")
    has_unit = any(row.get(field, "") for field in IMPORT_REQUIRED_UNIT_FIELDS)
    row_fingerprint = hashlib.sha256("|".join(row.get(key, "") for key in sorted(row.keys())).encode("utf-8")).hexdigest()
    if row_fingerprint in seen_row_fingerprints:
        errors.append({"row": row_number, "error": "Repeated row in uploaded file."})
    seen_row_fingerprints.add(row_fingerprint)

    missing_site = [field for field in IMPORT_REQUIRED_SITE_FIELDS if not row.get(field, "")]
    if missing_site:
        errors.append({"row": row_number, "error": f"Missing required site fields: {', '.join(sorted(missing_site))}"})
    if site_code:
        site_key = site_code.lower()
        if site_key in seen_site_codes:
            warnings.append({"row": row_number, "warning": f"Repeated site code in file: {site_code}"})
        seen_site_codes.add(site_key)

    site_type = row.get("site_type", "")
    if site_type and site_type not in {choice[0] for choice in MediaSite.SiteType.choices}:
        errors.append({"row": row_number, "error": f"Invalid site_type: {site_type}"})

    latitude = _parse_decimal(row.get("site_latitude", ""), field="site_latitude", row_number=row_number, errors=errors)
    longitude = _parse_decimal(row.get("site_longitude", ""), field="site_longitude", row_number=row_number, errors=errors)
    if latitude is None or longitude is None:
        warnings.append({"row": row_number, "warning": "Coordinates are empty and can be verified later through POE."})
    else:
        if latitude < Decimal("-90") or latitude > Decimal("90") or longitude < Decimal("-180") or longitude > Decimal("180"):
            errors.append({"row": row_number, "error": "Coordinates are outside valid latitude/longitude bounds."})
        elif not (Decimal("6") <= latitude <= Decimal("38") and Decimal("68") <= longitude <= Decimal("98")):
            warnings.append({"row": row_number, "warning": "Coordinates are outside the usual India operating range. Review before confirming."})

    if has_unit:
        missing_unit = [field for field in IMPORT_REQUIRED_UNIT_FIELDS if not row.get(field, "")]
        if missing_unit:
            errors.append({"row": row_number, "error": f"Missing required unit fields: {', '.join(sorted(missing_unit))}"})
        if unit_code.lower() in seen_unit_codes:
            errors.append({"row": row_number, "error": f"Repeated media unit code in file: {unit_code}"})
        if unit_code:
            seen_unit_codes.add(unit_code.lower())
        if unit_code and MediaUnit.objects.filter(unit_code__iexact=unit_code).exists():
            warnings.append({"row": row_number, "warning": f"Media unit already exists and will be skipped: {unit_code}"})
        _parse_int(row.get("face_count", ""), field="face_count", row_number=row_number, errors=errors)
        width = _parse_decimal(row.get("width", ""), field="width", row_number=row_number, errors=errors, required=True)
        height = _parse_decimal(row.get("height", ""), field="height", row_number=row_number, errors=errors, required=True)
        if width is not None and width <= 0:
            errors.append({"row": row_number, "error": "width must be greater than zero."})
        if height is not None and height <= 0:
            errors.append({"row": row_number, "error": "height must be greater than zero."})
        _parse_decimal(row.get("monthly_rate", ""), field="monthly_rate", row_number=row_number, errors=errors, required=True)
        status = row.get("status", "") or MediaUnit.Status.AVAILABLE
        if status not in {choice[0] for choice in MediaUnit.Status.choices}:
            errors.append({"row": row_number, "error": f"Invalid media unit status: {status}"})
        unit_site_type = row.get("unit_site_type", "") or row.get("media_unit_site_type", "") or row.get("unit_type", "")
        if unit_site_type and unit_site_type not in {choice[0] for choice in MediaUnit.SiteType.choices}:
            errors.append({"row": row_number, "error": f"Invalid unit_site_type: {unit_site_type}"})

    duplicate_site = bool(site_code and MediaSite.objects.filter(code__iexact=site_code).exists())
    if duplicate_site:
        warnings.append({"row": row_number, "warning": f"Site already exists and will be updated safely: {site_code}"})

    return {
        "row": row_number,
        "status": "failed" if errors else "warning" if warnings else "valid",
        "action": "update_site" if duplicate_site else "create_site",
        "site_code": site_code,
        "site_name": row.get("site_name", ""),
        "unit_code": unit_code,
        "errors": errors,
        "warnings": warnings,
        "data": row,
    }


def _build_import_summary(preview_rows: list[dict[str, Any]]) -> dict[str, int]:
    valid_rows = sum(1 for row in preview_rows if row["status"] == "valid")
    warning_rows = sum(1 for row in preview_rows if row["status"] == "warning")
    failed_rows = sum(1 for row in preview_rows if row["status"] == "failed")
    duplicate_rows = sum(
        1
        for row in preview_rows
        if any("already exists" in item.get("warning", "") or "Repeated" in item.get("warning", "") for item in row.get("warnings", []))
        or any("Repeated" in item.get("error", "") for item in row.get("errors", []))
    )
    rows_to_import = valid_rows + warning_rows
    return {
        "valid_rows": valid_rows,
        "warning_rows": warning_rows,
        "failed_rows": failed_rows,
        "duplicate_rows": duplicate_rows,
        "rows_to_import": rows_to_import,
        "rows_skipped": failed_rows,
    }


def validate_inventory_sites_import(file_obj, *, actor=None) -> ImportExportJob:
    rows, raw, filename = _read_inventory_import_rows(file_obj)
    seen_unit_codes: set[str] = set()
    seen_site_codes: set[str] = set()
    seen_row_fingerprints: set[str] = set()
    preview_rows = [
        _validate_inventory_row(
            row,
            row_number=index,
            seen_unit_codes=seen_unit_codes,
            seen_site_codes=seen_site_codes,
            seen_row_fingerprints=seen_row_fingerprints,
        )
        for index, row in enumerate(rows, start=2)
    ]
    errors = [item for row in preview_rows for item in row["errors"]]
    warnings = [item for row in preview_rows for item in row["warnings"]]
    summary = _build_import_summary(preview_rows)
    import_hash = hashlib.sha256(raw).hexdigest()
    status = ImportExportJob.Status.PREVIEWED
    job = ImportExportJob.objects.create(
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        job_type=ImportExportJob.JobType.IMPORT,
        resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
        status=status,
        rows_total=len(preview_rows),
        rows_success=summary["rows_to_import"],
        rows_failed=summary["failed_rows"],
        errors=errors,
        filters={
            "warnings": warnings,
            "summary": summary,
            "import_hash": import_hash,
            "no_records_imported": True,
            "duplicate_handling": "Existing sites are updated; existing media units are skipped; repeated unit codes in the file are rejected.",
        },
        preview_rows=preview_rows,
    )
    job.original_file.save(filename, ContentFile(raw), save=True)
    record_audit_event(
        event_type="inventory.import.previewed",
        entity_type="import_export_job",
        entity_id=job.id,
        actor=actor,
        severity=AuditEvent.Severity.WARNING if errors or warnings else AuditEvent.Severity.INFO,
        summary=f"Inventory import previewed: {summary['rows_to_import']} importable, {summary['failed_rows']} failed.",
        metadata={"job_id": job.id, "summary": summary},
    )
    return job


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "illuminated"}


def _decimal_or_none(value: str):
    if value == "":
        return None
    return Decimal(value)


def _write_import_error_report(job: ImportExportJob, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["row", "site_code", "unit_code", "status", "message"])
    for row in rows:
        status = row.get("status", "")
        messages = []
        messages.extend(item.get("error", "") for item in row.get("errors", []))
        messages.extend(item.get("warning", "") for item in row.get("warnings", []) if status in {"skipped", "failed"})
        if row.get("message"):
            messages.append(row["message"])
        for message in messages or [""]:
            writer.writerow([row.get("row", ""), row.get("site_code", ""), row.get("unit_code", ""), status, message])
    filename = f"inventory-import-{job.id}-report.csv"
    job.output_file.save(filename, ContentFile(output.getvalue().encode("utf-8")), save=False)


def _reset_preview_row_for_retry(row: dict[str, Any]) -> dict[str, Any]:
    reset = {**row}
    reset.pop("status", None)
    reset.pop("message", None)
    # Processing failures add generic row errors. Preview validation errors should
    # remain rare here because only importable preview rows can be confirmed, but
    # keeping row data/warnings intact lets the idempotent importer decide safely.
    if reset.get("data"):
        reset["errors"] = []
    return reset


def _import_ready_inventory_row(row: dict[str, Any], *, actor=None) -> tuple[str, dict[str, Any]]:
    if row.get("errors"):
        return "failed", {**row, "status": "failed", "message": "Row failed preview validation."}

    data = row.get("data") or {}
    site_code = data.get("site_code", "")
    unit_code = data.get("unit_code", "")
    site = MediaSite.objects.filter(code__iexact=site_code).first()
    action = row.get("action") or "create_site"

    if site and action != "update_site":
        return "skipped", {**row, "status": "skipped", "message": f"Site already exists and was not marked update-safe: {site_code}"}
    if not site and action == "update_site":
        return "skipped", {**row, "status": "skipped", "message": f"Site no longer exists for update: {site_code}"}

    site_defaults = {
        "name": data.get("site_name", ""),
        "site_type": data.get("site_type", ""),
        "address": data.get("address", ""),
        "city": data.get("city", ""),
        "state": data.get("state", ""),
        "owner": actor if getattr(actor, "is_authenticated", False) else None,
    }
    latitude = _decimal_or_none(data.get("site_latitude", ""))
    longitude = _decimal_or_none(data.get("site_longitude", ""))
    if latitude is not None and longitude is not None:
        site_defaults["latitude"] = latitude
        site_defaults["longitude"] = longitude
        site_defaults["location_status"] = MediaSite.LocationStatus.PROVISIONAL
        site_defaults["location_source"] = MediaSite.LocationSource.MANUAL

    if site:
        for field, value in site_defaults.items():
            setattr(site, field, value)
        site.save()
        site_result = "updated"
    else:
        site = MediaSite.objects.create(code=site_code, **site_defaults)
        site_result = "imported"

    if unit_code:
        if MediaUnit.objects.filter(unit_code__iexact=unit_code).exists():
            return "skipped", {**row, "status": "skipped", "message": f"Media unit already exists and was skipped: {unit_code}"}
        MediaUnit.objects.create(
            site=site,
            unit_code=unit_code,
            face_count=_parse_int(data.get("face_count", ""), field="face_count", row_number=row.get("row", 0), errors=[]),
            width=Decimal(data.get("width", "0")),
            height=Decimal(data.get("height", "0")),
            monthly_rate=Decimal(data.get("monthly_rate", "0")),
            status=data.get("status") or MediaUnit.Status.AVAILABLE,
            is_illuminated=_parse_bool(data.get("is_illuminated", "")),
            facing_direction=data.get("facing_direction", ""),
            site_type=data.get("unit_site_type", "") or data.get("media_unit_site_type", "") or data.get("unit_type", ""),
        )

    return site_result, {**row, "status": site_result}


def process_inventory_sites_import(job: ImportExportJob, *, actor=None) -> ImportExportJob:
    if job.job_type != ImportExportJob.JobType.IMPORT or job.resource_type != ImportExportJob.ResourceType.INVENTORY_SITES:
        raise ValueError("Only inventory site import jobs can be processed here.")
    if job.company_name != get_company_name():
        raise ValueError("Import job does not belong to the active company.")
    if job.status == ImportExportJob.Status.COMPLETED:
        return job
    if job.status not in {ImportExportJob.Status.CONFIRMED, ImportExportJob.Status.PROCESSING}:
        raise ValueError("Only confirmed inventory import jobs can be processed.")

    rows = list(job.preview_rows or [])
    if not job.filters.get("source_preview_rows"):
        job.filters = {**job.filters, "source_preview_rows": rows}
    started_at = job.started_at or timezone.now()
    job.status = ImportExportJob.Status.PROCESSING
    job.started_at = started_at
    job.rows_success = 0
    job.rows_updated = 0
    job.rows_skipped = 0
    job.rows_failed = 0
    job.errors = []
    job.save(update_fields=["status", "started_at", "rows_success", "rows_updated", "rows_skipped", "rows_failed", "errors", "filters", "updated_at"])

    imported_count = 0
    updated_count = 0
    skipped_count = 0
    failed_rows: list[dict[str, Any]] = []
    processed_rows: list[dict[str, Any]] = []

    for row in rows:
        try:
            with transaction.atomic():
                result, processed = _import_ready_inventory_row(row, actor=actor)
        except Exception:
            processed = {**row, "status": "failed", "message": "Row could not be imported.", "errors": [*row.get("errors", []), {"row": row.get("row"), "error": "Row could not be imported safely."}]}
            result = "failed"

        processed_rows.append(processed)
        if result == "imported":
            imported_count += 1
        elif result == "updated":
            updated_count += 1
        elif result == "skipped":
            skipped_count += 1
        else:
            failed_rows.extend(processed.get("errors") or [{"row": processed.get("row"), "error": processed.get("message", "Row failed.")}])

        job.rows_success = imported_count
        job.rows_updated = updated_count
        job.rows_skipped = skipped_count
        job.rows_failed = len(failed_rows)
        job.preview_rows = processed_rows + rows[len(processed_rows):]
        job.save(update_fields=["rows_success", "rows_updated", "rows_skipped", "rows_failed", "preview_rows", "updated_at"])

    job.errors = failed_rows
    job.preview_rows = processed_rows
    job.completed_at = timezone.now()
    job.status = ImportExportJob.Status.FAILED if failed_rows and not (imported_count or updated_count or skipped_count) else ImportExportJob.Status.COMPLETED
    job.filters = {
        **job.filters,
        "no_records_imported": False,
        "summary": {
            **job.filters.get("summary", {}),
            "imported_count": imported_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "failed_count": len(failed_rows),
            "duration_seconds": max(0, int((job.completed_at - started_at).total_seconds())),
        },
    }
    if failed_rows or skipped_count:
        _write_import_error_report(job, processed_rows)
    job.save(update_fields=["status", "rows_success", "rows_updated", "rows_skipped", "rows_failed", "errors", "preview_rows", "filters", "completed_at", "output_file", "updated_at"])

    severity = AuditEvent.Severity.WARNING if job.rows_failed or job.rows_skipped else AuditEvent.Severity.INFO
    record_audit_event(
        event_type="inventory.import.completed" if job.status == ImportExportJob.Status.COMPLETED else "inventory.import.failed",
        entity_type="import_export_job",
        entity_id=job.id,
        actor=actor,
        severity=severity,
        summary=f"Inventory import finished: {imported_count} imported, {updated_count} updated, {skipped_count} skipped, {len(failed_rows)} failed.",
        metadata={"job_id": job.id, "rows_total": job.rows_total, "summary": job.filters.get("summary", {})},
    )
    try:
        from apps.notifications.services import NotificationService

        NotificationService().notify_operations(
            event_type=EmailNotificationLog.NotificationType.INVENTORY_IMPORT_FAILED if job.status == ImportExportJob.Status.FAILED else EmailNotificationLog.NotificationType.INVENTORY_IMPORT_COMPLETED,
            title="Inventory import failed" if job.status == ImportExportJob.Status.FAILED else "Inventory import completed",
            message=f"{imported_count} imported, {updated_count} updated, {skipped_count} skipped, {len(failed_rows)} failed.",
            severity="critical" if job.status == ImportExportJob.Status.FAILED else "warning" if job.rows_failed or job.rows_skipped else "info",
            metadata={"import_job_id": job.id, "rows_total": job.rows_total, "summary": job.filters.get("summary", {})},
        )
    except Exception:
        pass
    return job


def _dispatch_inventory_import_job(job: ImportExportJob, *, actor=None) -> ImportExportJob:
    if getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True) and not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        try:
            from .tasks import process_inventory_import_job

            async_result = process_inventory_import_job.delay(job.id, actor_id=getattr(actor, "id", None))
            job.filters = {**job.filters, "celery_task_id": getattr(async_result, "id", "")}
            job.save(update_fields=["filters", "updated_at"])
            return job
        except Exception as exc:
            job.filters = {**job.filters, "dispatch_warning": str(exc)}
            job.save(update_fields=["filters", "updated_at"])
    return process_inventory_sites_import(job, actor=actor)


def confirm_inventory_sites_import(job: ImportExportJob, *, actor=None, confirmed: bool = False) -> ImportExportJob:
    if not confirmed:
        raise ValueError("Explicit confirmation is required to start the import.")
    if job.company_name != get_company_name():
        raise ValueError("Import job does not belong to the active company.")
    if job.job_type != ImportExportJob.JobType.IMPORT or job.resource_type != ImportExportJob.ResourceType.INVENTORY_SITES:
        raise ValueError("Only inventory site import jobs can be confirmed here.")
    if job.status != ImportExportJob.Status.PREVIEWED:
        raise ValueError("Only previewed inventory import jobs can be confirmed.")
    if (job.filters.get("summary", {}).get("rows_to_import") or job.rows_success) <= 0:
        raise ValueError("There are no importable rows to start.")

    job.status = ImportExportJob.Status.CONFIRMED
    job.rows_success = 0
    job.rows_updated = 0
    job.rows_skipped = 0
    job.rows_failed = 0
    job.errors = []
    job.filters = {
        **job.filters,
        "confirmed_at": timezone.now().isoformat(),
        "confirmed_by": getattr(actor, "email", "") or getattr(actor, "username", ""),
    }
    job.save(update_fields=["status", "rows_success", "rows_updated", "rows_skipped", "rows_failed", "errors", "filters", "updated_at"])
    record_audit_event(
        event_type="inventory.import.confirmed",
        entity_type="import_export_job",
        entity_id=job.id,
        actor=actor,
        summary=f"Inventory import confirmed for {job.rows_total} row(s).",
        metadata={"job_id": job.id, "rows_total": job.rows_total, "summary": job.filters.get("summary", {})},
    )

    return _dispatch_inventory_import_job(job, actor=actor)


def retry_import_export_job(job: ImportExportJob, *, actor=None) -> ImportExportJob:
    if job.company_name != get_company_name():
        raise ValueError("Job does not belong to the active company.")
    if job.status != ImportExportJob.Status.FAILED:
        raise ValueError("Only failed import/export jobs can be retried.")

    now = timezone.now()
    next_retry_count = job.retry_count + 1
    if job.job_type == ImportExportJob.JobType.IMPORT:
        if job.resource_type != ImportExportJob.ResourceType.INVENTORY_SITES:
            raise ValueError("Only inventory import retries are supported.")
        source_rows = job.filters.get("source_preview_rows") or job.preview_rows
        retry_rows = [_reset_preview_row_for_retry(row) for row in source_rows]
        retry_job = ImportExportJob.objects.create(
            created_by=actor if getattr(actor, "is_authenticated", False) else job.created_by,
            company_name=job.company_name,
            job_type=job.job_type,
            resource_type=job.resource_type,
            status=ImportExportJob.Status.CONFIRMED,
            original_file=job.original_file,
            filters={
                **job.filters,
                "retry_of_job_id": job.id,
                "retry_attempt": next_retry_count,
                "retry_requested_at": now.isoformat(),
                "retry_requested_by": getattr(actor, "email", "") or getattr(actor, "username", ""),
                "source_preview_rows": source_rows,
            },
            retry_of=job,
            retry_count=next_retry_count,
            rows_total=job.rows_total,
            preview_rows=retry_rows,
        )
        event_type = "inventory.import.retry_requested"
        summary = f"Inventory import retry requested for failed job #{job.id}."
    elif job.job_type == ImportExportJob.JobType.EXPORT:
        retry_job = ImportExportJob.objects.create(
            created_by=actor if getattr(actor, "is_authenticated", False) else job.created_by,
            company_name=job.company_name,
            job_type=job.job_type,
            resource_type=job.resource_type,
            status=ImportExportJob.Status.CONFIRMED,
            filters={
                **job.filters,
                "retry_of_job_id": job.id,
                "retry_attempt": next_retry_count,
                "retry_requested_at": now.isoformat(),
                "retry_requested_by": getattr(actor, "email", "") or getattr(actor, "username", ""),
            },
            retry_of=job,
            retry_count=next_retry_count,
        )
        event_type = "export.retry_requested"
        summary = f"{job.resource_type} export retry requested for failed job #{job.id}."
    else:
        raise ValueError("Unsupported job type for retry.")

    job.retry_count = next_retry_count
    job.last_retry_at = now
    job.save(update_fields=["retry_count", "last_retry_at", "updated_at"])
    record_audit_event(
        event_type=event_type,
        entity_type="import_export_job",
        entity_id=job.id,
        actor=actor,
        severity=AuditEvent.Severity.WARNING,
        summary=summary,
        metadata={"job_id": job.id, "retry_job_id": retry_job.id, "retry_attempt": next_retry_count, "resource_type": job.resource_type},
    )

    if retry_job.job_type == ImportExportJob.JobType.IMPORT:
        return _dispatch_inventory_import_job(retry_job, actor=actor)
    return _dispatch_export_job(retry_job, actor=actor)


def _inventory_export_payload(filters=None) -> tuple[str, list[str], list[list[Any]]]:
    filters = filters or {}
    rows = list(
        scope_queryset_to_tenant_path(MediaSite.objects.order_by("code"), filters.get("_user")).values_list(
            "code", "name", "site_type", "address", "city", "state", "latitude", "longitude", "location_status"
        )
    )
    return "inventory-sites.csv", ["code", "name", "site_type", "address", "city", "state", "latitude", "longitude", "location_status"], rows


def _campaign_export_payload(filters=None) -> tuple[str, list[str], list[list[Any]]]:
    filters = filters or {}
    queryset = scope_queryset_to_tenant_path(
        Campaign.objects.select_related("client", "account_manager").order_by("-created_at"),
        filters.get("_user"),
    )
    if filters.get("status"):
        queryset = queryset.filter(status=filters["status"])
    if filters.get("client"):
        queryset = queryset.filter(client_id=filters["client"])
    rows = [
        [item.code, item.name, item.status, item.client.email, item.start_date, item.end_date, item.budget]
        for item in queryset
    ]
    return "campaigns.csv", ["code", "name", "status", "client", "start_date", "end_date", "budget"], rows


def _invoice_payment_export_payload(filters=None) -> tuple[str, list[str], list[list[Any]]]:
    filters = filters or {}
    queryset = scope_queryset_to_tenant_path(
        Invoice.objects.select_related("campaign", "campaign__client").prefetch_related("payments").order_by("-created_at"),
        filters.get("_user"),
        "campaign__tenant",
    )
    if filters.get("status"):
        queryset = queryset.filter(status=filters["status"])
    if filters.get("client"):
        queryset = queryset.filter(campaign__client_id=filters["client"])
    rows = []
    for invoice in queryset:
        payments = list(invoice.payments.all())
        if not payments:
            rows.append([
                invoice.invoice_number or invoice.id,
                invoice.campaign.name,
                invoice.campaign.client.email,
                invoice.status,
                invoice.invoice_date,
                invoice.due_date,
                invoice.total_amount,
                invoice.grand_total,
                "",
                "",
                "",
                "",
            ])
            continue
        for payment in payments:
            rows.append([
                invoice.invoice_number or invoice.id,
                invoice.campaign.name,
                invoice.campaign.client.email,
                invoice.status,
                invoice.invoice_date,
                invoice.due_date,
                invoice.total_amount,
                invoice.grand_total,
                payment.payment_date,
                payment.amount,
                payment.method,
                payment.reference_number,
            ])
    return (
        "invoice-payments.csv",
        ["invoice", "campaign", "client", "status", "invoice_date", "due_date", "total_amount", "grand_total", "payment_date", "payment_amount", "payment_method", "payment_reference"],
        rows,
    )


def _poe_export_payload(filters=None) -> tuple[str, list[str], list[list[Any]]]:
    filters = filters or {}
    queryset = scope_queryset_to_tenant_path(
        ProofOfExecution.objects.select_related("booking__campaign", "booking__media_unit__site", "checked_by").order_by("-captured_at"),
        filters.get("_user"),
        "booking__campaign__tenant",
    )
    if filters.get("campaign"):
        queryset = queryset.filter(booking__campaign_id=filters["campaign"])
    if filters.get("status"):
        queryset = queryset.filter(verification_status=filters["status"])
    rows = [
        [
            item.id,
            item.booking.campaign.name,
            item.booking.media_unit.site.name,
            item.verification_status,
            item.review_sla_status,
            item.captured_at,
            item.latitude,
            item.longitude,
        ]
        for item in queryset
    ]
    return "poe-report.csv", ["poe_id", "campaign", "site", "verification_status", "review_sla_status", "captured_at", "latitude", "longitude"], rows


def _client_statement_export_payload(filters=None) -> tuple[str, list[str], list[list[Any]]]:
    filters = filters or {}
    client_id = filters.get("client")
    queryset = scope_queryset_to_tenant_path(
        Invoice.objects.select_related("campaign", "campaign__client").order_by("-created_at"),
        filters.get("_user"),
        "campaign__tenant",
    )
    if client_id:
        queryset = queryset.filter(campaign__client_id=client_id)
    rows = []
    for invoice in queryset:
        paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or 0
        total = invoice.grand_total or invoice.total_amount
        rows.append([invoice.campaign.client.email, invoice.invoice_number or invoice.id, invoice.status, total, paid, total - paid])
    return "client-statement.csv", ["client", "invoice", "status", "total", "paid", "balance"], rows


EXPORT_PAYLOAD_BUILDERS = {
    ImportExportJob.ResourceType.INVENTORY_SITES: _inventory_export_payload,
    ImportExportJob.ResourceType.CAMPAIGNS: _campaign_export_payload,
    ImportExportJob.ResourceType.POE_REPORTS: _poe_export_payload,
    ImportExportJob.ResourceType.INVOICES: _invoice_payment_export_payload,
    ImportExportJob.ResourceType.CLIENT_STATEMENTS: _client_statement_export_payload,
}


def process_export_job(job: ImportExportJob, *, actor=None) -> ImportExportJob:
    if job.job_type != ImportExportJob.JobType.EXPORT:
        raise ValueError("Only export jobs can be processed here.")
    if job.company_name != get_company_name():
        raise ValueError("Export job does not belong to the active company.")
    if job.status == ImportExportJob.Status.COMPLETED:
        return job
    if job.status not in {ImportExportJob.Status.CONFIRMED, ImportExportJob.Status.PROCESSING}:
        raise ValueError("Only queued export jobs can be processed.")

    started_at = job.started_at or timezone.now()
    job.status = ImportExportJob.Status.PROCESSING
    job.started_at = started_at
    job.rows_success = 0
    job.rows_failed = 0
    job.errors = []
    job.save(update_fields=["status", "started_at", "rows_success", "rows_failed", "errors", "updated_at"])

    try:
        builder = EXPORT_PAYLOAD_BUILDERS[job.resource_type]
        export_filters = {**job.filters.get("export_filters", {}), "_user": actor}
        filename, header, rows = builder(export_filters)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(header)
        job.rows_total = len(rows)
        job.save(update_fields=["rows_total", "updated_at"])
        for row in rows:
            writer.writerow(row)
            job.rows_success += 1
            job.save(update_fields=["rows_success", "updated_at"])
        job.output_file.save(filename, ContentFile(output.getvalue().encode("utf-8")), save=False)
        job.completed_at = timezone.now()
        job.status = ImportExportJob.Status.COMPLETED
        job.filters = {
            **job.filters,
            "summary": {
                "exported_count": job.rows_success,
                "failed_count": 0,
                "duration_seconds": max(0, int((job.completed_at - started_at).total_seconds())),
            },
        }
        job.save(update_fields=["status", "rows_total", "rows_success", "output_file", "completed_at", "filters", "updated_at"])
        record_audit_event(
            event_type="export.completed",
            entity_type="import_export_job",
            entity_id=job.id,
            actor=actor,
            summary=f"{job.resource_type} export completed with {job.rows_success} row(s).",
            metadata={"job_id": job.id, "resource_type": job.resource_type, "rows_success": job.rows_success},
        )
        try:
            from apps.notifications.services import NotificationService

            NotificationService().notify_operations(
                event_type=EmailNotificationLog.NotificationType.EXPORT_COMPLETED,
                title="Export completed",
                message=f"{job.resource_type.replace('_', ' ')} export completed with {job.rows_success} row(s).",
                severity="info",
                metadata={"export_job_id": job.id, "resource_type": job.resource_type, "rows_success": job.rows_success},
            )
        except Exception:
            pass
        return job
    except Exception:
        job.status = ImportExportJob.Status.FAILED
        job.completed_at = timezone.now()
        job.rows_failed = 1
        job.errors = [{"error": "Export could not be generated safely."}]
        job.filters = {
            **job.filters,
            "summary": {
                "exported_count": job.rows_success,
                "failed_count": 1,
                "duration_seconds": max(0, int((job.completed_at - started_at).total_seconds())),
            },
        }
        job.save(update_fields=["status", "completed_at", "rows_failed", "errors", "filters", "updated_at"])
        record_audit_event(
            event_type="export.failed",
            entity_type="import_export_job",
            entity_id=job.id,
            actor=actor,
            severity=AuditEvent.Severity.ERROR,
            summary=f"{job.resource_type} export failed.",
            metadata={"job_id": job.id, "resource_type": job.resource_type},
        )
        try:
            from apps.notifications.services import NotificationService

            NotificationService().notify_operations(
                event_type=EmailNotificationLog.NotificationType.EXPORT_FAILED,
                title="Export failed",
                message=f"{job.resource_type.replace('_', ' ')} export could not be generated safely.",
                severity="critical",
                metadata={"export_job_id": job.id, "resource_type": job.resource_type},
            )
        except Exception:
            pass
        return job


def _dispatch_export_job(job: ImportExportJob, *, actor=None) -> ImportExportJob:
    if getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True) and not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        try:
            from .tasks import process_export_job_task

            async_result = process_export_job_task.delay(job.id, actor_id=getattr(actor, "id", None))
            job.filters = {**job.filters, "celery_task_id": getattr(async_result, "id", "")}
            job.save(update_fields=["filters", "updated_at"])
            return job
        except Exception as exc:
            job.filters = {**job.filters, "dispatch_warning": str(exc)}
            job.save(update_fields=["filters", "updated_at"])
    return process_export_job(job, actor=actor)


def _start_csv_export_job(*, actor=None, resource_type: str, filters=None) -> ImportExportJob:
    filters = filters or {}
    if resource_type not in EXPORT_PAYLOAD_BUILDERS:
        raise ValueError("Unsupported export type.")
    job = ImportExportJob.objects.create(
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        job_type=ImportExportJob.JobType.EXPORT,
        resource_type=resource_type,
        status=ImportExportJob.Status.CONFIRMED,
        filters={"export_filters": filters},
    )
    record_audit_event(
        event_type="export.queued",
        entity_type="import_export_job",
        entity_id=job.id,
        actor=actor,
        summary=f"{resource_type} export queued.",
        metadata={"job_id": job.id, "resource_type": resource_type, "filters": filters},
    )
    return _dispatch_export_job(job, actor=actor)


def export_inventory_sites_csv(*, actor=None, filters=None) -> ImportExportJob:
    return _start_csv_export_job(actor=actor, resource_type=ImportExportJob.ResourceType.INVENTORY_SITES, filters=filters)


def export_campaigns_csv(*, actor=None, filters=None) -> ImportExportJob:
    return _start_csv_export_job(actor=actor, resource_type=ImportExportJob.ResourceType.CAMPAIGNS, filters=filters)


def export_invoices_csv(*, actor=None, filters=None) -> ImportExportJob:
    return _start_csv_export_job(actor=actor, resource_type=ImportExportJob.ResourceType.INVOICES, filters=filters)


def export_poe_reports_csv(*, actor=None, filters=None) -> ImportExportJob:
    return _start_csv_export_job(actor=actor, resource_type=ImportExportJob.ResourceType.POE_REPORTS, filters=filters)


def export_client_statement_csv(*, actor=None, filters=None) -> ImportExportJob:
    return _start_csv_export_job(actor=actor, resource_type=ImportExportJob.ResourceType.CLIENT_STATEMENTS, filters=filters)
