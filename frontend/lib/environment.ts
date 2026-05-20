import { apiFetch } from "@/lib/auth";

export type OperationalMode = {
  mode: "normal" | "maintenance" | "degraded" | "read_only" | string;
  label: string;
  message: string;
  is_write_blocking: boolean;
  updated_at?: string | null;
  updated_by_email?: string | null;
};

export async function fetchOperationalMode() {
  return apiFetch<OperationalMode>("observability/operational-mode/");
}

export async function updateOperationalMode(input: { mode: string; message?: string }) {
  return apiFetch<OperationalMode>("observability/operational-mode/", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
