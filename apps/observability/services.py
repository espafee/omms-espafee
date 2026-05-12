from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import timedelta
from io import StringIO
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import connection, models
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.inventory.models import MediaSite
from apps.poe.models import ProofOfExecution
from apps.poe.services import resolve_review_sla_status
from core.repositories import BaseRepository
from core.services import BaseService

from .models import ApiRequestLog, AuditEvent, ImportExportJob


SENSITIVE_METADATA_KEYS = {"password", "token", "otp", "authorization", "secret", "private_key", "file", "image"}


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


def build_poe_analytics(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    queryset = ProofOfExecution.objects.select_related(
        "booking",
        "booking__campaign",
        "booking__media_unit",
        "booking__media_unit__site",
        "checked_by",
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


def build_role_activity(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    queryset = AuditEvent.objects.select_related("actor")
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
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database_ok = False

    cache_ok = cache.set("omms:diagnostics:ping", "ok", 10) and cache.get("omms:diagnostics:ping") == "ok"
    return {
        "app_version": getattr(settings, "OMMS_APP_VERSION", ""),
        "git_commit": getattr(settings, "OMMS_GIT_COMMIT", ""),
        "database": {"ok": database_ok},
        "cache": {"ok": bool(cache_ok), "timeout_seconds": getattr(settings, "OMMS_DASHBOARD_CACHE_SECONDS", 60)},
        "background_jobs": {
            "celery_broker_configured": bool(getattr(settings, "CELERY_BROKER_URL", "")),
            "mode": "celery-ready",
        },
        "request_logging": {
            "enabled": getattr(settings, "OMMS_API_REQUEST_LOGGING_ENABLED", True),
            "slow_threshold_ms": getattr(settings, "OMMS_SLOW_REQUEST_MS", 1000),
            "retention_days": getattr(settings, "OMMS_REQUEST_LOG_RETENTION_DAYS", 30),
        },
        "recent_slow_requests": list(
            ApiRequestLog.objects.filter(is_slow=True)
            .values("created_at", "method", "path", "status_code", "duration_ms", "category")[:10]
        ),
        "recent_errors": list(
            ApiRequestLog.objects.filter(status_code__gte=500)
            .values("created_at", "method", "path", "status_code", "duration_ms", "category")[:10]
        ),
    }


def export_inventory_sites_csv(*, actor=None) -> ImportExportJob:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["code", "name", "site_type", "address", "city", "state", "latitude", "longitude", "location_status"])
    rows = MediaSite.objects.order_by("code").values_list(
        "code", "name", "site_type", "address", "city", "state", "latitude", "longitude", "location_status"
    )
    row_count = 0
    for row in rows:
        writer.writerow(row)
        row_count += 1
    job = ImportExportJob.objects.create(
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        job_type=ImportExportJob.JobType.EXPORT,
        resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
        status=ImportExportJob.Status.COMPLETED,
        rows_total=row_count,
        rows_success=row_count,
    )
    job.output_file.save("inventory-sites.csv", ContentFile(output.getvalue().encode("utf-8")), save=True)
    return job


def validate_inventory_sites_import(file_obj, *, actor=None) -> ImportExportJob:
    raw = file_obj.read()
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    reader = csv.DictReader(StringIO(text))
    required = {"code", "name", "site_type", "address", "city", "state"}
    errors = []
    preview = []
    total = 0
    for index, row in enumerate(reader, start=2):
        total += 1
        missing = [field for field in required if not (row.get(field) or "").strip()]
        if missing:
            errors.append({"row": index, "error": f"Missing required fields: {', '.join(sorted(missing))}"})
        if len(preview) < 20:
            preview.append(row)
    job = ImportExportJob.objects.create(
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        job_type=ImportExportJob.JobType.IMPORT,
        resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
        status=ImportExportJob.Status.FAILED if errors else ImportExportJob.Status.VALIDATED,
        rows_total=total,
        rows_success=0 if errors else total,
        rows_failed=len(errors),
        errors=errors,
        preview_rows=preview,
    )
    job.original_file.save(getattr(file_obj, "name", "inventory-sites.csv"), ContentFile(text.encode("utf-8")), save=True)
    return job
