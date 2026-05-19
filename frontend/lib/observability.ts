import { apiFetch } from "@/lib/auth";

type Paginated<T> = {
  results: T[];
};

export type PoeAnalytics = {
  total_poes: number;
  suspicious_count: number;
  outside_geofence_count: number;
  missing_gps_count: number;
  duplicate_replacement_count: number;
  pending_review_count: number;
  overdue_review_count: number;
  trends_by_date: Array<{ day: string; total: number; suspicious: number }>;
  recent_suspicious: Array<{
    id: number;
    campaign: string;
    site: string;
    status: string;
    review_sla_status: string;
    captured_at: string;
  }>;
};

export type OperationsSummary = {
  poe: PoeAnalytics;
  poe_sla: {
    warning_count: number;
    breach_count: number;
    oldest_pending: {
      id: number;
      captured_at: string;
      campaign: string;
      age_hours: number;
    } | null;
    unassigned_count: number;
    reviewer_workload: Array<{
      reviewer: string;
      pending: number;
      approved: number;
      rejected: number;
      rework: number;
      is_overloaded: boolean;
    }>;
    suspicious_unresolved_count: number;
    thresholds: {
      pending_warning_hours: number;
      pending_breach_hours: number;
      suspicious_warning_hours: number;
      suspicious_breach_hours: number;
      reviewer_overload_threshold: number;
    };
  };
  kpis: {
    active_jobs: number;
    failed_jobs: number;
    suspicious_poes: number;
    pending_poe_reviews: number;
    poe_sla_warnings: number;
    poe_sla_breaches: number;
    notifications_today: number;
    failed_requests: number;
    active_users_today: number;
    campaigns_running: number;
    campaigns_ending_soon: number;
    campaigns_poe_risk: number;
    campaigns_billing_risk: number;
    critical_campaigns: number;
    invoice_collection_rate: number;
    overdue_invoices: number;
    overdue_invoice_value: string;
    export_activity_today: number;
  };
  billing_intelligence: {
    total_invoiced_amount: string;
    collected_amount: string;
    pending_amount: string;
    overdue_amount: string;
    overdue_invoice_count: number;
    collection_efficiency_percentage: number;
    average_days_to_payment: number | null;
    overdue_age_buckets: Array<{ bucket: string; label: string; count: number; amount: string }>;
    top_overdue_clients: Array<{ client: string; count: number; amount: string; oldest_days_overdue: number }>;
    payment_trend: Array<{ day: string; amount: string; payments: number }>;
  };
  campaign_performance: {
    active_campaigns: number;
    ending_soon_count: number;
    poe_risk_count: number;
    billing_risk_count: number;
    at_risk_count: number;
    critical_count: number;
    can_view_billing: boolean;
    risk_distribution: Array<{ risk: string; total: number }>;
    poe_completion_trend: Array<{ campaign: string; completion: number; missing: number }>;
    operational_health_trend: Array<{ campaign: string; risk: string; indicators: number }>;
    campaigns: Array<{
      campaign_id: number;
      campaign_name: string;
      campaign_code: string;
      risk_status: string;
      poe_completion_percentage: number;
      booked_sites_count: number;
      sites_with_approved_poe: number;
      sites_missing_poe: number;
      pending_poe_count: number;
      suspicious_poe_count: number;
      invoice_generated: boolean;
      billing_status: string;
      payment_collection_status: string;
      payment_completion_percentage: number;
      has_overdue_invoice: boolean;
      operational_delay_indicators: string[];
      pending_amount: string;
      overdue_amount: string;
      is_ending_soon: boolean;
    }>;
  };
  slow_requests_count: number;
  audit_by_severity: Array<{ severity: string; total: number }>;
  notification_failures_count: number;
  notification_retries_due: number;
  recent_critical_alerts: Array<{
    id: number;
    metric: string;
    summary: string;
    severity: string;
    created_at: string;
    acknowledged_at: string | null;
    acknowledged_by__email?: string | null;
  }>;
  charts: {
    job_activity: Array<{ day: string; imports: number; exports: number; failed: number }>;
    request_activity: Array<{ day: string; total: number; failed: number; slow: number; failed_percentage: number }>;
    poe_status: Array<{ verification_status: string; total: number }>;
    reviewer_workload: Array<{ reviewer: string; total: number }>;
    poe_reviewer_workload: Array<{
      reviewer: string;
      pending: number;
      approved: number;
      rejected: number;
      rework: number;
      is_overloaded: boolean;
    }>;
    billing_activity: Array<{ day: string; invoices: number; paid: number; overdue: number }>;
    payment_activity: Array<{ day: string; payments: number }>;
    operations_activity: Array<{ day: string; events: number }>;
    notification_activity: Array<{ day: string; notifications: number }>;
    load_distribution: Array<{ entity_type: string; total: number }>;
    campaign_risk_distribution: Array<{ risk: string; total: number }>;
    campaign_poe_completion_trend: Array<{ campaign: string; completion: number; missing: number }>;
    campaign_operational_health_trend: Array<{ campaign: string; risk: string; indicators: number }>;
  };
  timeline: Array<{
    id: string;
    kind: string;
    module: string;
    status: string;
    summary: string;
    actor: string;
    created_at: string;
  }>;
  system_health: {
    status: string;
    api_status: string;
    recent_failed_requests: number;
    recent_slow_requests: number;
    recent_failed_background_jobs: number;
    signals: string[];
    deployment: {
      environment_name: string;
      debug: boolean;
      frontend_url: string;
      backend_url: string;
      redis_configured: boolean;
      celery_eager: boolean;
      database_engine: string;
      app_version: string;
      git_commit: string;
    };
    celery: {
      enabled: boolean;
      broker_configured: boolean;
      eager: boolean;
      mode: string;
      worker_ready: string;
      beat_configured: boolean;
    };
    redis: { configured: boolean };
    database: { ok: boolean };
    celery_mode: string;
    broker_configured: boolean;
    active_jobs: number;
    failed_jobs: number;
    api_failure_count: number;
    api_failure_percentage: number;
    last_successful_import: string | null;
    last_successful_export: string | null;
    notification_retries_due: number;
  };
};

export type DiagnosticsPayload = {
  app_version: string;
  git_commit: string;
  environment: OperationsSummary["system_health"]["deployment"];
  system_health: OperationsSummary["system_health"];
  database: { ok: boolean };
  cache: { ok: boolean; timeout_seconds: number };
  background_jobs: {
    celery_broker_configured: boolean;
    background_jobs_enabled: boolean;
    mode: string;
    worker_ready: string;
    beat_configured: boolean;
  };
  request_logging: { enabled: boolean; slow_threshold_ms: number; retention_days: number };
  recent_slow_requests: Array<{
    created_at: string;
    method: string;
    path: string;
    status_code: number;
    duration_ms: number;
    category: string;
  }>;
  recent_errors: Array<{
    created_at: string;
    method: string;
    path: string;
    status_code: number;
    duration_ms: number;
    category: string;
  }>;
};

export type AuditEvent = {
  id: number;
  event_type: string;
  entity_type: string;
  entity_id: string;
  severity: string;
  summary: string;
  actor_email?: string;
  created_at: string;
};

export type ImportExportJob = {
  id: number;
  job_type: string;
  resource_type: string;
  status: string;
  rows_total: number;
  rows_success: number;
  rows_updated: number;
  rows_skipped: number;
  rows_failed: number;
  errors: Array<{ row?: number; error: string }>;
  filters: {
    warnings?: Array<{ row?: number; warning: string }>;
    summary?: Record<string, number>;
    duplicate_handling?: string;
    no_records_imported?: boolean;
    celery_task_id?: string;
  };
  preview_rows: Array<{
    row?: number;
    status?: string;
    action?: string;
    site_code?: string;
    site_name?: string;
    unit_code?: string;
    errors?: Array<{ row?: number; error: string }>;
    warnings?: Array<{ row?: number; warning: string }>;
    message?: string;
  }>;
  original_file_url: string;
  output_file_url: string;
  retry_of_id?: number | null;
  retry_count: number;
  last_retry_at: string | null;
  created_by_email?: string;
  progress_percent: number;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
};

export type AlertRule = {
  id: number;
  name: string;
  metric: string;
  threshold: number;
  window_minutes: number;
  cooldown_minutes: number;
  severity: string;
  is_enabled: boolean;
  current_value: number;
  last_triggered_at: string | null;
  cooldown_until: string | null;
  cooldown_remaining_minutes: number;
  updated_at: string;
};

export type AlertEvent = {
  id: number;
  metric: string;
  summary: string;
  severity: string;
  created_at: string;
  acknowledged_at: string | null;
  acknowledged_by_email?: string | null;
  is_acknowledged: boolean;
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchPoeAnalytics() {
  return apiFetch<PoeAnalytics>("observability/poe-analytics/");
}

function toQuery(params: Record<string, string>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      search.set(key, value);
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export async function fetchOperationsSummary(filters: Record<string, string> = {}) {
  return apiFetch<OperationsSummary>(`observability/operations-summary/${toQuery(filters)}`);
}

export async function fetchDiagnostics() {
  return apiFetch<DiagnosticsPayload>("observability/diagnostics/");
}

export async function fetchAuditEvents(filters: Record<string, string> = {}) {
  return list<AuditEvent>(`observability/audit-events/${toQuery({ page_size: "10", ...filters })}`);
}

export async function uploadInventorySiteImport(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<ImportExportJob>("observability/import-export-jobs/inventory-sites/import-preview/", {
    method: "POST",
    body: formData,
  });
}

export async function fetchImportJob(id: number) {
  return apiFetch<ImportExportJob>(`observability/import-export-jobs/${id}/`);
}

export async function confirmImportJob(id: number) {
  return apiFetch<ImportExportJob>(`observability/import-export-jobs/${id}/confirm/`, {
    method: "POST",
    body: JSON.stringify({ confirmed: true }),
  });
}

export async function retryImportExportJob(id: number) {
  return apiFetch<ImportExportJob>(`observability/import-export-jobs/${id}/retry/`, {
    method: "POST",
  });
}

export async function fetchExportJobs() {
  return list<ImportExportJob>("observability/import-export-jobs/?job_type=export&page_size=8");
}

export async function createExportJob(path: "inventory-sites" | "campaigns" | "invoices" | "poe-reports" | "client-statements", filters: Record<string, string> = {}) {
  return apiFetch<ImportExportJob>(`observability/import-export-jobs/${path}/export/`, {
    method: "POST",
    body: JSON.stringify(filters),
  });
}

export async function fetchAlertRules() {
  return list<AlertRule>("observability/alert-rules/?page_size=20");
}

export async function updateAlertRule(id: number, input: Partial<Pick<AlertRule, "threshold" | "is_enabled" | "cooldown_minutes" | "window_minutes">>) {
  return apiFetch<AlertRule>(`observability/alert-rules/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function acknowledgeAlertEvent(id: number) {
  return apiFetch<AlertEvent>(`observability/alert-events/${id}/acknowledge/`, {
    method: "POST",
  });
}
