import { ApiError, apiFetch } from "@/lib/auth";
import type { Booking } from "@/lib/bookings";
import type { Campaign } from "@/lib/campaigns";
import type { InventorySite, InventoryUnit } from "@/lib/inventory";

type Paginated<T> = {
  results: T[];
};

export type PoeMedia = {
  id: number;
  poe_record: number;
  image?: string | null;
  image_url: string | null;
  media_url: string;
  media_type: string;
  captured_at: string;
  captured_by: number | null;
  note: string;
  created_at: string;
  updated_at: string;
};

export type PoeRecord = {
  id: number;
  booking: number;
  executed_on: string;
  captured_at: string;
  latitude: string | null;
  longitude: string | null;
  checked_by: number | null;
  verification_status: string;
  verification_score: string | null;
  verification_notes: string;
  notes: string;
  media_items: PoeMedia[];
  created_at: string;
  updated_at: string;
};

export type PoePayload = {
  records: PoeRecord[];
  bookings: Booking[];
  campaigns: Campaign[];
  sites: InventorySite[];
  units: InventoryUnit[];
};

export type PoeWorkflowInput = {
  record: {
    booking: number;
    executed_on: string;
    verification_status: string;
    notes: string;
    checked_by: number | null;
  };
  evidence: Array<{
    image: File;
    media_type: string;
    captured_at: string;
  }>;
};

export type PoeWorkflowResult = {
  record: PoeRecord;
  evidence: PoeMedia[];
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export function getPoeCreateError(error: unknown) {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      fieldErrors: error.fieldErrors,
      partialSuccess: false,
    };
  }
  return {
    message: error instanceof Error ? error.message : "Unable to create proof of execution.",
    fieldErrors: {},
    partialSuccess: false,
  };
}

export async function fetchPoeData(): Promise<PoePayload> {
  const [records, bookings, campaigns, sites, units] = await Promise.all([
    list<PoeRecord>("poe/"),
    list<Booking>("bookings/"),
    list<Campaign>("campaigns/"),
    list<InventorySite>("inventory/sites/"),
    list<InventoryUnit>("inventory/units/"),
  ]);
  return { records, bookings, campaigns, sites, units };
}

export async function createPoeWorkflow(payload: PoeWorkflowInput): Promise<PoeWorkflowResult> {
  const record = await apiFetch<PoeRecord>("poe/", {
    method: "POST",
    body: JSON.stringify(payload.record),
  });

  const evidence: PoeMedia[] = [];
  for (const item of payload.evidence) {
    const formData = new FormData();
    formData.append("poe_record", String(record.id));
    formData.append("image", item.image);
    formData.append("media_type", item.media_type);
    formData.append("captured_at", item.captured_at);

    evidence.push(
      await apiFetch<PoeMedia>("poe/media/", {
        method: "POST",
        body: formData,
      }),
    );
  }

  return { record, evidence };
}
