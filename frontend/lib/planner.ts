import { apiFetch } from "@/lib/auth";

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";

export type Availability = { status: string; label: string; reason: string; conflict_count: number };
export type PublicPlannerImage = { url: string; caption: string; is_primary: boolean };
export type PublicPlannerUnit = {
  public_id: string;
  unit_code: string;
  location_name: string;
  public_address: string;
  city: string;
  region: string;
  dimensions: { width: string; height: string };
  display_format: string;
  facing_direction: string;
  is_illuminated: boolean;
  availability: Availability;
  description: string;
  features: string[];
  primary_photo: PublicPlannerImage | null;
  photos: PublicPlannerImage[];
  image_download_allowed: boolean;
  monthly_rate: string | null;
  map?: { latitude: string | null; longitude: string | null };
};
export type PublicPlannerPayload = {
  count: number;
  next: string | null;
  previous: string | null;
  results: PublicPlannerUnit[];
  planner: {
    title: string;
    tenant_name: string;
    client_name: string;
    contact_email: string;
    expires_at: string | null;
    show_rates: boolean;
    pricing_mode: string;
    allow_proposal_submission: boolean;
    allow_image_download: boolean;
    client_rate_card_available: boolean;
  };
  filters: {
    cities: string[];
    locations: string[];
    formats: string[];
    facing_directions: string[];
    illumination: Array<{ value: string; label: string }>;
    availability_statuses: string[];
    rate_bounds: { min: string | null; max: string | null };
  };
  meta: {
    eligible_unit_count: number;
    eligible_count_before_filters?: number;
    results_count?: number;
    empty_reason?: "no_eligible_inventory" | "no_date_availability" | "no_filter_matches" | null;
    has_campaign_dates: boolean;
  };
};
export type PlannerProposalLine = {
  id: number;
  unit_public_id: string;
  unit_code: string;
  location_name: string;
  city: string;
  monthly_rate_snapshot: string | null;
  availability_status: string;
  current_availability: Availability;
  photo_url: string | null;
};
export type PlannerProposal = {
  id: number;
  reference: string;
  client_name: string;
  campaign_name: string;
  brand_company: string;
  requested_start_date: string;
  requested_end_date: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  billing_gstin: string;
  notes: string;
  status: string;
  submitted_at: string;
  preliminary_subtotal: string;
  selected_unit_count: number;
  availability_conflict_count: number;
  assigned_to_name: string;
  estimate_number: string | null;
  converted_campaign_code: string | null;
  lines: PlannerProposalLine[];
  audit_events: Array<{ event_type: string; summary: string; severity: string; actor: string; created_at: string }>;
};
export type PlannerLink = {
  id: number;
  tenant?: number;
  tenant_name?: string;
  title: string;
  client: number | null;
  client_name: string;
  allowed_cities: string[];
  allowed_regions: string[];
  allowed_inventory_types: string[];
  show_rates: boolean;
  pricing_mode: string;
  effective_show_rates?: boolean;
  allow_proposal_submission: boolean;
  allow_image_download: boolean;
  allow_map_data: boolean;
  expires_at: string | null;
  revoked_at: string | null;
  is_available: boolean;
  eligible_unit_count?: number;
  public_path?: string;
  token?: string;
  created_at?: string;
  updated_at?: string;
};
export type PlannerEligibilityPreview = {
  counts: {
    base_media_units: number;
    tenant_scoped: number;
    publicly_listed: number;
    operational: number;
    allowed_city: number;
    date_available: number;
    eligible: number;
  };
  excluded: {
    not_published: number;
    city_not_allowed: number;
    inactive: number;
    unavailable_for_dates: number;
    missing_public_information: number;
  };
  allowed_cities: string[];
};
export type PlannerLinkEligibilityDiagnostics = {
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
  link: {
    id: number;
    title: string;
    tenant_id: number;
    tenant_name: string;
    active: boolean;
    revoked: boolean;
    expired: boolean;
    allowed_cities_type: string;
    allowed_cities: string[];
    pricing_mode: string;
    expires_at: string | null;
    eligible_count: number;
    published_count: number;
    excluded_count: number;
  };
  pipeline: Record<string, number>;
  exclusions: Record<string, number>;
  sample_units: Array<{
    code: string;
    tenant_id: number | null;
    published: boolean;
    status: string;
    public_id_present: boolean;
    city_raw: string;
    city_normalized: string;
    parent_active: boolean;
    eligible: boolean;
    exclusion_reason: string | null;
  }>;
};

function queryString(values: Record<string, string | number | boolean | undefined | null>) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  return query.toString();
}

async function publicRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT.replace(/\/$/, "")}/${path.replace(/^\//, "")}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || Object.values(payload).flat().join(" ") || "The media planner request could not be completed.");
  }
  return response.json() as Promise<T>;
}

export function fetchPublicPlanner(token: string, filters: Record<string, string | number | boolean | undefined>) {
  return publicRequest<PublicPlannerPayload>(`public/media-planner/${encodeURIComponent(token)}/?${queryString(filters)}`);
}

export function submitPublicProposal(token: string, payload: Record<string, unknown>) {
  return publicRequest<{ reference: string; status: string; message: string }>(
    `public/media-planner/${encodeURIComponent(token)}/proposals/`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function fetchPlannerLinks() {
  const payload = await apiFetch<{ results: PlannerLink[] } | PlannerLink[]>("planner/links/");
  return Array.isArray(payload) ? payload : payload.results;
}
export function createPlannerLink(payload: Record<string, unknown>) {
  return apiFetch<PlannerLink>("planner/links/", { method: "POST", body: JSON.stringify(payload) });
}
export function revokePlannerLink(id: number) {
  return apiFetch<PlannerLink>(`planner/links/${id}/revoke/`, { method: "POST", body: "{}" });
}
export function fetchPlannerLinkEligibility(id: number) {
  return apiFetch<PlannerEligibilityPreview>(`planner/links/${id}/eligible-inventory/`);
}
export function fetchPlannerLinkEligibilityDiagnostics(id: number, params: Record<string, string> = {}) {
  const query = queryString(params);
  return apiFetch<PlannerLinkEligibilityDiagnostics>(
    `planner/links/${id}/eligibility-diagnostics/${query ? `?${query}` : ""}`,
  );
}
export async function fetchPlannerProposals(filters: Record<string, string> = {}) {
  const payload = await apiFetch<{ results: PlannerProposal[] } | PlannerProposal[]>(`planner/proposals/?${queryString(filters)}`);
  return Array.isArray(payload) ? payload : payload.results;
}
export function fetchPlannerProposal(id: string | number) {
  return apiFetch<PlannerProposal>(`planner/proposals/${id}/`);
}
export function plannerProposalAction<T>(id: number, action: string, body: Record<string, unknown> = {}) {
  return apiFetch<T>(`planner/proposals/${id}/${action}/`, { method: "POST", body: JSON.stringify(body) });
}
