const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";

export type PublicImage = {
  id: number;
  image_url: string | null;
  caption: string;
  is_primary: boolean;
};

export type PublicAsset = {
  id: number;
  name: string;
  asset_type: string;
  file_url: string;
  version: string;
};

export type PublicPoeMedia = {
  id: number;
  image_url: string | null;
  media_url: string;
  media_type: string;
  captured_at: string;
};

export type PublicPoeRecord = {
  id: number;
  executed_on: string;
  captured_at: string;
  verification_status: string;
  verification_score: string | null;
  verification_notes: string;
  media_items: PublicPoeMedia[];
};

export type PublicBooking = {
  id: number;
  status: string;
  start_date: string;
  end_date: string;
  site: {
    id: number;
    name: string;
    code: string;
    city: string;
    state: string;
    primary_image: PublicImage | null;
  };
  media_unit: {
    id: number;
    unit_code: string;
    status: string;
    is_illuminated: boolean;
    facing_direction: string;
    site_type: string;
    primary_image: PublicImage | null;
  };
  poe_records: PublicPoeRecord[];
};

export type PublicCampaignAccessPayload = {
  campaign: {
    id: number;
    name: string;
    code: string;
    status: string;
    objective: string;
    start_date: string;
    end_date: string;
    assets: PublicAsset[];
    bookings: PublicBooking[];
  };
  access_expires_at: string | null;
  link_status: string;
};

export class PublicCampaignAccessError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "PublicCampaignAccessError";
    this.status = status;
    this.code = code;
  }
}

function getFallbackPublicAccessMessage(status: number) {
  if (status === 404) {
    return "This campaign link does not exist or is no longer available.";
  }
  if (status === 410) {
    return "This campaign link is no longer active.";
  }
  if (status >= 500) {
    return "The campaign link is temporarily unavailable. Please try again in a moment.";
  }
  return "This campaign link is not available right now.";
}

export async function fetchPublicCampaignAccess(token: string): Promise<PublicCampaignAccessPayload> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT.replace(/\/$/, "")}/campaigns/public/${token}/`, { cache: "no-store" });
  } catch {
    throw new PublicCampaignAccessError(
      "We couldn't reach the server for this campaign link. Please try again.",
      0,
      "network_error",
    );
  }

  if (!response.ok) {
    let payload: { detail?: string; code?: string } = {};
    try {
      payload = (await response.json()) as typeof payload;
    } catch {
      payload = {};
    }
    throw new PublicCampaignAccessError(
      payload.detail || getFallbackPublicAccessMessage(response.status),
      response.status,
      payload.code ?? "access_unavailable",
    );
  }
  return response.json() as Promise<PublicCampaignAccessPayload>;
}
