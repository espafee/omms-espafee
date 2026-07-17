import { apiFetch } from "@/lib/auth";
import type { CampaignSummary } from "@/lib/dashboard";

type Paginated<T> = {
  results: T[];
};

export type CampaignAsset = {
  id: number;
  campaign: number;
  name: string;
  asset_type: string;
  file_url: string;
  version: string;
  is_approved: boolean;
  created_at: string;
  updated_at: string;
};

export type Campaign = {
  id: number;
  name: string;
  code: string;
  client: number;
  account_manager: number | null;
  start_date: string;
  end_date: string;
  budget: string;
  status: string;
  effective_status: "upcoming" | "ongoing" | "ended" | "paused" | "cancelled";
  is_ended: boolean;
  is_ongoing: boolean;
  is_upcoming: boolean;
  objective: string;
  assets: CampaignAsset[];
  performance?: {
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
  } | null;
  created_at: string;
  updated_at: string;
};

export type CampaignCreateInput = {
  name: string;
  code: string;
  client: number;
  account_manager: number | null;
  start_date: string;
  end_date: string;
  budget: string;
  status: string;
  objective: string;
};

export type CampaignPayload = {
  campaigns: Campaign[];
  summary: CampaignSummary;
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchCampaignData(): Promise<CampaignPayload> {
  const [campaigns, summary] = await Promise.all([
    list<Campaign>("campaigns/"),
    apiFetch<CampaignSummary>("campaigns/summary/"),
  ]);
  return { campaigns, summary };
}

export async function fetchCampaign(campaignId: number) {
  return apiFetch<Campaign>(`campaigns/${campaignId}/`);
}

export async function createCampaign(payload: CampaignCreateInput) {
  return apiFetch<Campaign>("campaigns/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
