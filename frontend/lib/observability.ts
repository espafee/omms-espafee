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
  }>;
};

export type DiagnosticsPayload = {
  app_version: string;
  git_commit: string;
  database: { ok: boolean };
  cache: { ok: boolean; timeout_seconds: number };
  background_jobs: { celery_broker_configured: boolean; background_jobs_enabled: boolean; mode: string };
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
  created_by_email?: string;
  progress_percent: number;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
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

export async function fetchExportJobs() {
  return list<ImportExportJob>("observability/import-export-jobs/?job_type=export&page_size=8");
}

export async function createExportJob(path: "inventory-sites" | "campaigns" | "invoices" | "poe-reports" | "client-statements", filters: Record<string, string> = {}) {
  return apiFetch<ImportExportJob>(`observability/import-export-jobs/${path}/export/`, {
    method: "POST",
    body: JSON.stringify(filters),
  });
}
