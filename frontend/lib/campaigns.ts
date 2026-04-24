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
  objective: string;
  assets: CampaignAsset[];
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

export async function createCampaign(payload: CampaignCreateInput) {
  return apiFetch<Campaign>("campaigns/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
