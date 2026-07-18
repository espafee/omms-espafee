import { apiFetch } from "@/lib/auth";

export type MediaPlannerDiagnosticsPayload = {
  service: {
    git_sha: string;
    build_timestamp: string;
    environment: string;
  };
  database: {
    engine: string;
    database_fingerprint: string;
    migration_status: Record<string, boolean>;
  };
  planner_link: {
    id: number;
    title: string;
    tenant_id: number;
    tenant_name: string;
    is_active: boolean;
    is_revoked: boolean;
    is_expired: boolean;
    allowed_cities_raw_type: string;
    allowed_cities_safe_summary: string[];
    allowed_cities_normalized: string[];
    pricing_mode: string;
    expires_at: string | null;
    eligible_count: number;
  };
  pipeline: Record<string, number>;
  exclusions: Record<string, number>;
  units: Array<{
    code: string;
    tenant_id: number | null;
    published: boolean;
    public_id_present: boolean;
    status: string;
    availability_status: string;
    city_raw: string;
    city_normalized: string;
    parent_active: boolean;
    eligible: boolean;
    exclusion_reason: string | null;
  }>;
};

export function fetchMediaPlannerDiagnostics(params: {
  planner_link_id?: string;
  planner_title?: string;
  unit_code?: string;
  requested_start_date?: string;
  requested_end_date?: string;
}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value);
    }
  });
  return apiFetch<MediaPlannerDiagnosticsPayload>(`platform/diagnostics/media-planner/?${query.toString()}`);
}

