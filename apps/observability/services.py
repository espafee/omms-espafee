from __future__ import annotations

import csv
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
from apps.campaigns.models import Campaign
from apps.billing.models import Invoice, Payment
from apps.issues.models import Issue
from apps.notifications.models import EmailNotificationLog
from apps.poe.models import ProofOfExecution
from apps.poe.services import resolve_review_sla_status
from core.repositories import BaseRepository
from core.services import BaseService

from .models import AlertEvent, AlertRule, ApiRequestLog, AuditEvent, ImportExportJob


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


class AlertRuleRepository(BaseRepository):
    model = AlertRule


class AlertEventRepository(BaseRepository):
    model = AlertEvent
    select_related = ("rule",)


class AlertRuleService(BaseService):
    repository_class = AlertRuleRepository


class AlertEventService(BaseService):
    repository_class = AlertEventRepository


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


def ensure_default_alert_rules() -> None:
    defaults = [
        ("Slow requests in last hour", AlertRule.Metric.SLOW_REQUESTS, 10, 60, AlertRule.Severity.WARNING),
        ("Failed notifications in last hour", AlertRule.Metric.FAILED_NOTIFICATIONS, 3, 60, AlertRule.Severity.WARNING),
        ("Suspicious POEs today", AlertRule.Metric.SUSPICIOUS_POES, 5, 1440, AlertRule.Severity.WARNING),
        ("Overdue POE reviews", AlertRule.Metric.OVERDUE_POE_REVIEWS, 5, 1440, AlertRule.Severity.WARNING),
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
    if rule.metric == AlertRule.Metric.FAILED_NOTIFICATIONS:
        return EmailNotificationLog.objects.filter(status=EmailNotificationLog.Status.FAILED, updated_at__gte=since).count()
    if rule.metric == AlertRule.Metric.SUSPICIOUS_POES:
        return ProofOfExecution.objects.filter(
            verification_status__in=[ProofOfExecution.VerificationStatus.SUSPICIOUS, ProofOfExecution.VerificationStatus.REJECTED],
            created_at__gte=since,
        ).count()
    if rule.metric == AlertRule.Metric.OVERDUE_POE_REVIEWS:
        return ProofOfExecution.objects.filter(reviewed_at__isnull=True, review_due_at__lt=now).count()
    if rule.metric == AlertRule.Metric.BREACHED_ISSUES:
        return Issue.objects.filter(sla_status=Issue.SlaStatus.BREACHED).exclude(status=Issue.Status.RESOLVED).count()
    if rule.metric == AlertRule.Metric.OVERDUE_INVOICES:
        return Invoice.objects.filter(status=Invoice.Status.OVERDUE).count()
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
        except Exception:
            pass
        created_events.append(event)
    return created_events


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


def build_operations_summary(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    poe_payload = build_poe_analytics(filters)
    request_queryset = ApiRequestLog.objects.all()
    audit_queryset = AuditEvent.objects.all()
    notification_queryset = EmailNotificationLog.objects.all()
    alert_queryset = AlertEvent.objects.select_related("rule")
    if filters.get("date_from"):
        request_queryset = request_queryset.filter(created_at__date__gte=filters["date_from"])
        audit_queryset = audit_queryset.filter(created_at__date__gte=filters["date_from"])
        notification_queryset = notification_queryset.filter(created_at__date__gte=filters["date_from"])
        alert_queryset = alert_queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        request_queryset = request_queryset.filter(created_at__date__lte=filters["date_to"])
        audit_queryset = audit_queryset.filter(created_at__date__lte=filters["date_to"])
        notification_queryset = notification_queryset.filter(created_at__date__lte=filters["date_to"])
        alert_queryset = alert_queryset.filter(created_at__date__lte=filters["date_to"])
    if filters.get("severity"):
        audit_queryset = audit_queryset.filter(severity=filters["severity"])
        alert_queryset = alert_queryset.filter(severity=filters["severity"])
    if filters.get("event_type"):
        audit_queryset = audit_queryset.filter(event_type=filters["event_type"])

    return {
        "poe": poe_payload,
        "slow_requests_count": request_queryset.filter(is_slow=True).count(),
        "audit_by_severity": list(audit_queryset.values("severity").annotate(total=Count("id")).order_by("severity")),
        "notification_failures_count": notification_queryset.filter(status=EmailNotificationLog.Status.FAILED).count(),
        "notification_retries_due": notification_queryset.filter(
            status=EmailNotificationLog.Status.FAILED,
            next_retry_at__lte=timezone.now(),
        ).count(),
        "recent_critical_alerts": list(
            alert_queryset.filter(severity__in=[AlertRule.Severity.CRITICAL, AlertRule.Severity.WARNING])
            .values("id", "metric", "summary", "severity", "created_at")[:10]
        ),
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
            "background_jobs_enabled": getattr(settings, "OMMS_ENABLE_BACKGROUND_JOBS", True),
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
        "recent_critical_alerts": list(
            AlertEvent.objects.filter(severity=AlertRule.Severity.CRITICAL)
            .values("created_at", "metric", "summary", "observed_value", "threshold")[:10]
        ),
        "notification_retry_health": {
            "failed_count": EmailNotificationLog.objects.filter(status=EmailNotificationLog.Status.FAILED).count(),
            "due_retry_count": EmailNotificationLog.objects.filter(
                status=EmailNotificationLog.Status.FAILED,
                next_retry_at__lte=timezone.now(),
            ).count(),
        },
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
    warnings = []
    preview = []
    total = 0
    for index, row in enumerate(reader, start=2):
        total += 1
        missing = [field for field in required if not (row.get(field) or "").strip()]
        if missing:
            errors.append({"row": index, "error": f"Missing required fields: {', '.join(sorted(missing))}"})
        code = (row.get("code") or "").strip()
        if code and MediaSite.objects.filter(code__iexact=code).exists():
            errors.append({"row": index, "error": f"Duplicate site code already exists: {code}"})
        if not (row.get("latitude") and row.get("longitude")):
            warnings.append({"row": index, "warning": "Coordinates are empty and can be captured during first verified POE."})
        if len(preview) < 20:
            preview.append(row)
    job = ImportExportJob.objects.create(
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        job_type=ImportExportJob.JobType.IMPORT,
        resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
        status=ImportExportJob.Status.FAILED if errors else ImportExportJob.Status.PREVIEWED,
        rows_total=total,
        rows_success=0 if errors else total,
        rows_failed=len(errors),
        errors=errors,
        filters={"warnings": warnings},
        preview_rows=preview,
    )
    job.original_file.save(getattr(file_obj, "name", "inventory-sites.csv"), ContentFile(text.encode("utf-8")), save=True)
    return job


def confirm_inventory_sites_import(job: ImportExportJob, *, actor=None) -> ImportExportJob:
    if job.job_type != ImportExportJob.JobType.IMPORT or job.resource_type != ImportExportJob.ResourceType.INVENTORY_SITES:
        raise ValueError("Only inventory site import jobs can be confirmed here.")
    if job.errors:
        job.status = ImportExportJob.Status.FAILED
        job.save(update_fields=["status", "updated_at"])
        return job

    job.status = ImportExportJob.Status.PROCESSING
    job.save(update_fields=["status", "updated_at"])
    success_count = 0
    errors = []
    valid_site_types = {choice[0] for choice in MediaSite.SiteType.choices}
    if job.original_file:
        raw = job.original_file.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        rows = list(csv.DictReader(StringIO(text)))
    else:
        rows = job.preview_rows
    for index, row in enumerate(rows, start=2):
        code = (row.get("code") or "").strip()
        if not code or MediaSite.objects.filter(code__iexact=code).exists():
            errors.append({"row": index, "error": f"Duplicate or missing site code: {code}"})
            continue
        site_type = (row.get("site_type") or "").strip()
        if site_type not in valid_site_types:
            errors.append({"row": index, "error": f"Invalid site type: {site_type}"})
            continue
        MediaSite.objects.create(
            code=code,
            name=(row.get("name") or "").strip(),
            site_type=site_type,
            address=(row.get("address") or "").strip(),
            city=(row.get("city") or "").strip(),
            state=(row.get("state") or "").strip(),
            latitude=(row.get("latitude") or None),
            longitude=(row.get("longitude") or None),
            owner=actor if getattr(actor, "is_authenticated", False) else None,
        )
        success_count += 1
    job.rows_success = success_count
    job.rows_failed = len(errors)
    job.errors = errors
    job.status = ImportExportJob.Status.FAILED if errors else ImportExportJob.Status.COMPLETED
    job.save(update_fields=["rows_success", "rows_failed", "errors", "status", "updated_at"])
    return job


def _create_csv_export_job(*, actor=None, resource_type: str, filename: str, header: list[str], rows: list[list[Any]], filters=None) -> ImportExportJob:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    job = ImportExportJob.objects.create(
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        company_name=get_company_name(),
        job_type=ImportExportJob.JobType.EXPORT,
        resource_type=resource_type,
        status=ImportExportJob.Status.COMPLETED,
        rows_total=len(rows),
        rows_success=len(rows),
        filters=filters or {},
    )
    job.output_file.save(filename, ContentFile(output.getvalue().encode("utf-8")), save=True)
    return job


def export_campaigns_csv(*, actor=None, filters=None) -> ImportExportJob:
    filters = filters or {}
    queryset = Campaign.objects.select_related("client", "account_manager").order_by("-created_at")
    if filters.get("status"):
        queryset = queryset.filter(status=filters["status"])
    if filters.get("client"):
        queryset = queryset.filter(client_id=filters["client"])
    rows = [
        [item.code, item.name, item.status, item.client.email, item.start_date, item.end_date, item.budget]
        for item in queryset
    ]
    return _create_csv_export_job(
        actor=actor,
        resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
        filename="campaigns.csv",
        header=["code", "name", "status", "client", "start_date", "end_date", "budget"],
        rows=rows,
        filters=filters,
    )


def export_invoices_csv(*, actor=None, filters=None) -> ImportExportJob:
    filters = filters or {}
    queryset = Invoice.objects.select_related("campaign", "campaign__client").order_by("-created_at")
    if filters.get("status"):
        queryset = queryset.filter(status=filters["status"])
    if filters.get("client"):
        queryset = queryset.filter(campaign__client_id=filters["client"])
    rows = [
        [item.invoice_number or item.id, item.campaign.name, item.campaign.client.email, item.status, item.invoice_date, item.due_date, item.total_amount, item.grand_total]
        for item in queryset
    ]
    return _create_csv_export_job(
        actor=actor,
        resource_type=ImportExportJob.ResourceType.INVOICES,
        filename="invoices.csv",
        header=["invoice", "campaign", "client", "status", "invoice_date", "due_date", "total_amount", "grand_total"],
        rows=rows,
        filters=filters,
    )


def export_poe_reports_csv(*, actor=None, filters=None) -> ImportExportJob:
    filters = filters or {}
    queryset = ProofOfExecution.objects.select_related("booking__campaign", "booking__media_unit__site", "checked_by").order_by("-captured_at")
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
    return _create_csv_export_job(
        actor=actor,
        resource_type=ImportExportJob.ResourceType.POE_REPORTS,
        filename="poe-report.csv",
        header=["poe_id", "campaign", "site", "verification_status", "review_sla_status", "captured_at", "latitude", "longitude"],
        rows=rows,
        filters=filters,
    )


def export_client_statement_csv(*, actor=None, filters=None) -> ImportExportJob:
    filters = filters or {}
    client_id = filters.get("client")
    queryset = Invoice.objects.select_related("campaign", "campaign__client").order_by("-created_at")
    if client_id:
        queryset = queryset.filter(campaign__client_id=client_id)
    rows = []
    for invoice in queryset:
        paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or 0
        total = invoice.grand_total or invoice.total_amount
        rows.append([invoice.campaign.client.email, invoice.invoice_number or invoice.id, invoice.status, total, paid, total - paid])
    return _create_csv_export_job(
        actor=actor,
        resource_type=ImportExportJob.ResourceType.CLIENT_STATEMENTS,
        filename="client-statement.csv",
        header=["client", "invoice", "status", "total", "paid", "balance"],
        rows=rows,
        filters=filters,
    )
