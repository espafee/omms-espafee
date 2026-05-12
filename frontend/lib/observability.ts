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

export type DiagnosticsPayload = {
  app_version: string;
  git_commit: string;
  database: { ok: boolean };
  cache: { ok: boolean; timeout_seconds: number };
  background_jobs: { celery_broker_configured: boolean; mode: string };
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

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchPoeAnalytics() {
  return apiFetch<PoeAnalytics>("observability/poe-analytics/");
}

export async function fetchDiagnostics() {
  return apiFetch<DiagnosticsPayload>("observability/diagnostics/");
}

export async function fetchAuditEvents() {
  return list<AuditEvent>("observability/audit-events/?page_size=10");
}
