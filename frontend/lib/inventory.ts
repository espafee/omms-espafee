import { ApiError, apiFetch } from "@/lib/auth";

type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type InventoryImage = {
  id: number;
  site?: number;
  media_unit?: number;
  image?: string;
  image_url: string | null;
  caption: string;
  is_primary: boolean;
  uploaded_by: number | null;
  uploaded_at: string;
  created_at: string;
  updated_at: string;
};

export type InventorySite = {
  id: number;
  name: string;
  code: string;
  site_type: string;
  address: string;
  city: string;
  state: string;
  latitude: string | null;
  longitude: string | null;
  owner: number | null;
  primary_image: InventoryImage | null;
  image_gallery: InventoryImage[];
  created_at: string;
  updated_at: string;
};

export type InventoryUnit = {
  id: number;
  site: number;
  unit_code: string;
  face_count: number;
  width: string;
  height: string;
  status: string;
  is_illuminated: boolean;
  monthly_rate: string;
  facing_direction: string;
  site_type: string;
  primary_image: InventoryImage | null;
  image_gallery: InventoryImage[];
  created_at: string;
  updated_at: string;
};

export type InventoryPayload = {
  sites: InventorySite[];
  units: InventoryUnit[];
};

export type InventorySiteCreateInput = {
  name: string;
  code: string;
  site_type: string;
  address: string;
  city: string;
  state: string;
  latitude: string | null;
  longitude: string | null;
};

export type InventoryUnitMutationInput = {
  site: number;
  unit_code: string;
  face_count: number;
  width: string;
  height: string;
  status: string;
  is_illuminated: boolean;
  monthly_rate: string;
  facing_direction: string;
  site_type: string;
};

export const MEDIA_UNIT_SITE_TYPE_OPTIONS = [
  { value: "single_side", label: "Single Side" },
  { value: "both_side", label: "Both Side" },
];

export function formatMediaUnitSiteType(value: string | null | undefined) {
  if (!value) {
    return "Type pending";
  }
  if (value === "single_side_view") {
    return "Single Side";
  }
  if (value === "both_side_view" || value === "back_to_back_double_site") {
    return "Both Side";
  }
  return MEDIA_UNIT_SITE_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value.replaceAll("_", " ");
}

export function normalizeMutationError(error: unknown) {
  if (error instanceof ApiError) {
    const fieldMessages = Object.entries(error.fieldErrors)
      .flatMap(([field, messages]) => messages.map((message) => `${field.replaceAll("_", " ")}: ${message}`))
      .join(" ");
    return {
      message: fieldMessages || error.message,
      fieldErrors: error.fieldErrors,
    };
  }
  return {
    message: error instanceof Error ? error.message : "Unable to save changes.",
    fieldErrors: {},
  };
}

export const getInventorySiteMutationError = normalizeMutationError;
export const getInventoryUnitMutationError = normalizeMutationError;

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchInventoryData(): Promise<InventoryPayload> {
  const [sites, units] = await Promise.all([
    list<InventorySite>("inventory/sites/"),
    list<InventoryUnit>("inventory/units/"),
  ]);
  return { sites, units };
}

export async function createSite(payload: InventorySiteCreateInput) {
  return apiFetch<InventorySite>("inventory/sites/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteSite(siteId: number) {
  return apiFetch<void>(`inventory/sites/${siteId}/`, {
    method: "DELETE",
  });
}

export async function createMediaUnit(payload: InventoryUnitMutationInput) {
  return apiFetch<InventoryUnit>("inventory/units/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateMediaUnit(unitId: number, payload: InventoryUnitMutationInput) {
  return apiFetch<InventoryUnit>(`inventory/units/${unitId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
