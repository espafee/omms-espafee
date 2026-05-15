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
    company_name = models.CharField(max_length=255, blank=True)
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    resource_type = models.CharField(max_length=40, choices=ResourceType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    original_file = models.FileField(upload_to="imports/", blank=True, null=True, max_length=500)
    output_file = models.FileField(upload_to="exports/", blank=True, null=True, max_length=500)
    filters = models.JSONField(default=dict, blank=True)
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


class AlertRule(TimeStampedModel):
    class Metric(models.TextChoices):
        SLOW_REQUESTS = "slow_requests", "Slow Requests"
        FAILED_NOTIFICATIONS = "failed_notifications", "Failed Notifications"
        SUSPICIOUS_POES = "suspicious_poes", "Suspicious POEs"
        OVERDUE_POE_REVIEWS = "overdue_poe_reviews", "Overdue POE Reviews"
        BREACHED_ISSUES = "breached_issues", "Breached Issues"
        OVERDUE_INVOICES = "overdue_invoices", "Overdue Invoices"

    class Severity(models.TextChoices):
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    name = models.CharField(max_length=120)
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
    metric = models.CharField(max_length=40, db_index=True)
    observed_value = models.PositiveIntegerField(default=0)
    threshold = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=20, db_index=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["metric", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.summary
