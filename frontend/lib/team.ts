import { apiFetch } from "@/lib/auth";

export type TeamRole = {
  key: string;
  value: string;
  label: string;
  description: string;
  capabilities: string[];
};

export type TeamTenant = {
  id: number;
  name: string;
  slug: string;
};

export type TeamUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone_number: string;
  role: string;
  role_label: string;
  region: string;
  reports_to: number | null;
  reports_to_name: string;
  tenant: number;
  tenant_name: string;
  assigned_work_count: number;
  managed_campaign_count: number;
  assigned_work_summary: string;
  last_login: string | null;
  is_active: boolean;
  account_status: "active" | "inactive" | "setup_pending";
  has_usable_password: boolean;
  setup_sent_at: string | null;
  created_at: string;
  updated_at: string;
  setup_delivery?: "sent" | "failed" | "not_requested";
};

export type TeamDirectory = {
  count: number;
  next: string | null;
  previous: string | null;
  results: TeamUser[];
};

export type TeamRoleDirectory = {
  roles: TeamRole[];
  tenants: TeamTenant[];
  can_select_tenant: boolean;
};

export type TeamUserInput = {
  email?: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  role: string;
  region: string;
  reports_to: number | null;
  tenant?: number;
  send_setup?: boolean;
};

function buildQuery(filters: Record<string, string>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      query.set(key, value);
    }
  }
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

export function fetchTeamUsers(filters: Record<string, string> = {}) {
  return apiFetch<TeamDirectory>(`team/users/${buildQuery(filters)}`);
}

export function fetchTeamRoles() {
  return apiFetch<TeamRoleDirectory>("team/roles/");
}

export function createTeamUser(payload: TeamUserInput) {
  return apiFetch<TeamUser>("team/users/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTeamUser(id: number, payload: TeamUserInput) {
  return apiFetch<TeamUser>(`team/users/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deactivateTeamUser(id: number) {
  return apiFetch<TeamUser>(`team/users/${id}/deactivate/`, { method: "POST", body: "{}" });
}

export function reactivateTeamUser(id: number) {
  return apiFetch<TeamUser>(`team/users/${id}/reactivate/`, { method: "POST", body: "{}" });
}

export function sendTeamUserSetup(id: number) {
  return apiFetch<TeamUser>(`team/users/${id}/send-setup/`, { method: "POST", body: "{}" });
}

export function completeAccountSetup(payload: { uid: string; token: string; password: string }) {
  return apiFetch<{ detail: string; is_active: boolean }>("team/account-setup/complete/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
