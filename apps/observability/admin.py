from django.contrib import admin

from .models import ApiRequestLog, AuditEvent, ImportExportJob


@admin.register(ApiRequestLog)
class ApiRequestLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "method", "path", "status_code", "duration_ms", "is_slow", "category", "user")
    list_filter = ("is_slow", "category", "method", "status_code", "created_at")
    search_fields = ("path", "user__email", "user_agent", "company_name")
    readonly_fields = [field.name for field in ApiRequestLog._meta.fields]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "entity_type", "entity_id", "severity", "actor", "summary")
    list_filter = ("event_type", "entity_type", "severity", "created_at")
    search_fields = ("summary", "actor__email", "campaign_reference", "client_reference", "invoice_reference")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]


@admin.register(ImportExportJob)
class ImportExportJobAdmin(admin.ModelAdmin):
    list_display = ("created_at", "job_type", "resource_type", "status", "rows_total", "rows_failed", "created_by")
    list_filter = ("job_type", "resource_type", "status", "created_at")
    search_fields = ("company_name", "created_by__email")
