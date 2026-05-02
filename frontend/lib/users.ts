import { apiFetch } from "@/lib/auth";

type Paginated<T> = {
  results: T[];
};

export type ClientOption = {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  phone_number?: string;
  organization_name: string;
};

export type ClientCreateInput = Omit<ClientOption, "id"> & {
  password: string;
  is_active: boolean;
};

export type UserOption = ClientOption & {
  role: string;
  is_active?: boolean;
};

export type FieldStaffOption = {
  id: number;
  email: string;
  name?: string;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone_number?: string;
  role: string;
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchClients() {
  return list<ClientOption>("users/clients/");
}

export async function createClient(payload: ClientCreateInput) {
  return apiFetch<ClientOption>("users/clients/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchUsers() {
  return list<UserOption>("users/");
}

export async function fetchFieldStaff() {
  return list<FieldStaffOption>("users/field-staff/");
}
