from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ApiRequestLog(models.Model):
    class Category(models.TextChoices):
        AUTH = "auth", "Auth"
        BILLING = "billing", "Billing"
        CAMPAIGNS = "campaigns", "Campaigns"
        INVENTORY = "inventory", "Inventory"
        BOOKINGS = "bookings", "Bookings"
        POE = "poe", "POE"
        ISSUES = "issues", "Issues"
        NOTIFICATIONS = "notifications", "Notifications"
        SETUP = "setup", "Setup"
        MOBILE = "mobile", "Mobile"
        OBSERVABILITY = "observability", "Observability"
        OTHER = "other", "Other"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="api_request_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    company_name = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=12)
    path = models.CharField(max_length=500, db_index=True)
    status_code = models.PositiveSmallIntegerField()
    duration_ms = models.PositiveIntegerField(default=0, db_index=True)
    is_slow = models.BooleanField(default=False, db_index=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    query_count = models.PositiveIntegerField(null=True, blank=True)
    query_time_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_slow", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path} [{self.status_code}]"


class AuditEvent(TimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    event_type = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=80, db_index=True)
    entity_id = models.CharField(max_length=80, blank=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="audit_events",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    company_name = models.CharField(max_length=255, blank=True)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO, db_index=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    campaign_reference = models.CharField(max_length=120, blank=True, db_index=True)
    client_reference = models.CharField(max_length=120, blank=True, db_index=True)
    invoice_reference = models.CharField(max_length=120, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} - {self.summary}"


class ImportExportJob(TimeStampedModel):
    class JobType(models.TextChoices):
        IMPORT = "import", "Import"
        EXPORT = "export", "Export"

    class ResourceType(models.TextChoices):
        INVENTORY_SITES = "inventory_sites", "Inventory Sites"
        MEDIA_UNITS = "media_units", "Media Units"
        CLIENTS = "clients", "Clients"
        CAMPAIGNS = "campaigns", "Campaigns"
        INVOICES = "invoices", "Invoices"
        CLIENT_STATEMENTS = "client_statements", "Client Statements"
        POE_REPORTS = "poe_reports", "POE Reports"

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PREVIEWED = "previewed", "Previewed"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        PENDING = "pending", "Pending"
        VALIDATED = "validated", "Validated"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="import_export_jobs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        related_name="import_export_jobs",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    company_name = models.CharField(max_length=255, blank=True)
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    resource_type = models.CharField(max_length=40, choices=ResourceType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    original_file = models.FileField(upload_to="imports/", blank=True, null=True, max_length=500)
    output_file = models.FileField(upload_to="exports/", blank=True, null=True, max_length=500)
    filters = models.JSONField(default=dict, blank=True)
    retry_of = models.ForeignKey(
        "self",
        related_name="retry_attempts",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    retry_count = models.PositiveIntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    rows_total = models.PositiveIntegerField(default=0)
    rows_success = models.PositiveIntegerField(default=0)
    rows_updated = models.PositiveIntegerField(default=0)
    rows_skipped = models.PositiveIntegerField(default=0)
    rows_failed = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    preview_rows = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job_type", "resource_type", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_type} {self.resource_type} ({self.status})"


class SavedOperationalView(TimeStampedModel):
    class ViewType(models.TextChoices):
        OPERATIONS = "operations", "Operations"
        SEARCH = "search", "Search"
        ALERTS = "alerts", "Alerts"
        CAMPAIGNS = "campaigns", "Campaigns"
        BILLING = "billing", "Billing"
        POE = "poe", "POE"
        IMPORT_EXPORT = "import_export", "Import / Export"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="saved_operational_views",
        on_delete=models.CASCADE,
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        related_name="saved_operational_views",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    company_name = models.CharField(max_length=255, blank=True, db_index=True)
    name = models.CharField(max_length=120)
    view_type = models.CharField(max_length=30, choices=ViewType.choices, default=ViewType.OPERATIONS, db_index=True)
    module = models.CharField(max_length=40, blank=True, db_index=True)
    search_query = models.CharField(max_length=120, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["view_type", "name"]
        unique_together = ("user", "company_name", "name")
        indexes = [
            models.Index(fields=["user", "view_type", "updated_at"]),
            models.Index(fields=["company_name", "module"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.view_type})"


class DashboardWidgetPreference(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="dashboard_widget_preferences",
        on_delete=models.CASCADE,
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        related_name="dashboard_widget_preferences",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    company_name = models.CharField(max_length=255, blank=True, db_index=True)
    widget_key = models.CharField(max_length=80)
    is_visible = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "widget_key"]
        unique_together = ("user", "company_name", "widget_key")
        indexes = [
            models.Index(fields=["user", "company_name", "sort_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.widget_key}: {'visible' if self.is_visible else 'hidden'}"


class OperationalMode(TimeStampedModel):
    class Mode(models.TextChoices):
        NORMAL = "normal", "Normal"
        MAINTENANCE = "maintenance", "Maintenance"
        DEGRADED = "degraded", "Degraded"
        READ_ONLY = "read_only", "Read Only"

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.NORMAL, db_index=True)
    message = models.CharField(max_length=255, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="operational_mode_updates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "operational mode"
        verbose_name_plural = "operational mode"

    def __str__(self) -> str:
        return self.get_mode_display()


class AlertRule(TimeStampedModel):
    class Metric(models.TextChoices):
        SLOW_REQUESTS = "slow_requests", "Slow Requests"
        FAILED_API_REQUESTS = "failed_api_requests", "Failed API Requests"
        FAILED_NOTIFICATIONS = "failed_notifications", "Failed Notifications"
        FAILED_IMPORT_EXPORT_JOBS = "failed_import_export_jobs", "Failed Import/Export Jobs"
        SUSPICIOUS_POES = "suspicious_poes", "Suspicious POEs"
        OVERDUE_POE_REVIEWS = "overdue_poe_reviews", "Overdue POE Reviews"
        POE_SLA_BREACHES = "poe_sla_breaches", "POE SLA Breaches"
        CAMPAIGNS_AT_RISK = "campaigns_at_risk", "Campaigns At Risk"
        SYSTEM_HEALTH_DEGRADED = "system_health_degraded", "System Health Degraded"
        BREACHED_ISSUES = "breached_issues", "Breached Issues"
        OVERDUE_INVOICES = "overdue_invoices", "Overdue Invoices"

    class Severity(models.TextChoices):
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    name = models.CharField(max_length=120)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        related_name="alert_rules",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    metric = models.CharField(max_length=40, choices=Metric.choices, unique=True)
    threshold = models.PositiveIntegerField(default=1)
    window_minutes = models.PositiveIntegerField(default=60)
    cooldown_minutes = models.PositiveIntegerField(default=60)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["metric"]

    def __str__(self) -> str:
        return f"{self.name} >= {self.threshold}"


class AlertEvent(TimeStampedModel):
    rule = models.ForeignKey(AlertRule, related_name="events", on_delete=models.CASCADE)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        related_name="alert_events",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    metric = models.CharField(max_length=40, db_index=True)
    observed_value = models.PositiveIntegerField(default=0)
    threshold = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=20, db_index=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        "users.User",
        related_name="acknowledged_alert_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["metric", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.summary
