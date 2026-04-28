import { ApiError, apiFetch } from "@/lib/auth";

const CACHE_KEY = "omms_campaign_share_links";

export type CampaignAccessLink = {
  id: number;
  campaign: number;
  public_path?: string | null;
  token_prefix: string;
  is_active: boolean;
  expires_at: string | null;
  revoked_at: string | null;
  created_by: number | null;
  revoked_by: number | null;
  last_accessed_at: string | null;
  created_at: string;
  updated_at: string;
  token?: string;
};

export type CampaignAccessLinkStatus = "active" | "expired" | "revoked" | "ended";

type Paginated<T> = {
  results: T[];
};

function readCache(): Record<string, string> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    return JSON.parse(window.localStorage.getItem(CACHE_KEY) ?? "{}") as Record<string, string>;
  } catch {
    return {};
  }
}

function writeCache(cache: Record<string, string>) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
}

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export function getCampaignAccessLinkStatus(link: CampaignAccessLink, campaignEndDate: string): CampaignAccessLinkStatus {
  const now = new Date();
  if (link.revoked_at || !link.is_active) {
    return "revoked";
  }
  if (link.expires_at && new Date(link.expires_at) <= now) {
    return "expired";
  }
  if (campaignEndDate && new Date(`${campaignEndDate}T23:59:59`) < now) {
    return "ended";
  }
  return "active";
}

export function getShareLinkStatusLabel(status: CampaignAccessLinkStatus) {
  return {
    active: "active",
    expired: "expired",
    revoked: "revoked",
    ended: "campaign ended",
  }[status];
}

export function getCachedCampaignShareLink(linkId: number, campaignId?: number) {
  const cache = readCache();
  if (campaignId) {
    return cache[`${campaignId}:${linkId}`] ?? null;
  }

  const suffix = `:${linkId}`;
  const matchedKey = Object.keys(cache).find((key) => key.endsWith(suffix));
  return matchedKey ? cache[matchedKey] : null;
}

export function getCampaignAccessLinkUrl(link: CampaignAccessLink | null) {
  if (!link) {
    return null;
  }

  if (link.public_path && typeof window !== "undefined") {
    return `${window.location.origin}${link.public_path}`;
  }

  return getCachedCampaignShareLink(link.id, link.campaign);
}

export function getCampaignShareLinkError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Unable to update campaign share link.";
}

export async function fetchCampaignAccessLinks() {
  return list<CampaignAccessLink>("campaigns/access-links/");
}

export async function createCampaignAccessLink(campaignId: number) {
  const link = await apiFetch<CampaignAccessLink>("campaigns/access-links/", {
    method: "POST",
    body: JSON.stringify({ campaign: campaignId }),
  });

  if (link.token && link.public_path) {
    const url = `${window.location.origin}${link.public_path}`;
    const cache = readCache();
    cache[`${campaignId}:${link.id}`] = url;
    writeCache(cache);
  }

  return link;
}

export async function revokeCampaignAccessLink(linkId: number) {
  return apiFetch<CampaignAccessLink>(`campaigns/access-links/${linkId}/revoke/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
