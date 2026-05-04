import { ApiError } from "@/lib/auth";

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";

function normalizeUrl(root: string, path: string) {
  return `${root.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

export type PublicEstimateLine = {
  id: number;
  description: string;
  start_date: string;
  end_date: string;
  quantity: string;
  unit_rate: string;
  tax_rate: string;
  taxable_amount: string;
  tax_amount: string;
  total_amount: string;
  media_unit_label: string;
  site_name: string;
};

export type PublicEstimatePayload = {
  id: number;
  estimate_number: string | null;
  title: string;
  status: string;
  start_date: string;
  end_date: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  notes: string;
  client_name: string;
  campaign_name: string;
  shared_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  client_response_comment: string;
  lines: PublicEstimateLine[];
};

export class PublicEstimateError extends Error {
  status: number;
  code: string;

  constructor(message: string, status = 0, code = "request_failed") {
    super(message);
    this.name = "PublicEstimateError";
    this.status = status;
    this.code = code;
  }
}

async function parsePublicResponse<T>(response: Response): Promise<T> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    if (payload && typeof payload === "object" && "detail" in payload) {
      const errorPayload = payload as { detail: unknown; code?: unknown };
      const detail = String(errorPayload.detail);
      const code = errorPayload.code ? String(errorPayload.code) : "request_failed";
      throw new PublicEstimateError(detail, response.status, code);
    }
    throw new PublicEstimateError("This estimate link is not available right now.", response.status, "request_failed");
  }

  return payload as T;
}

export async function fetchPublicEstimate(token: string) {
  const response = await fetch(normalizeUrl(API_ROOT, `public/estimates/${token}/`));
  return parsePublicResponse<PublicEstimatePayload>(response);
}

export async function submitPublicEstimateDecision(token: string, decision: "approve" | "reject", comment = "") {
  const response = await fetch(normalizeUrl(API_ROOT, `public/estimates/${token}/${decision}/`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ comment }),
  });
  return parsePublicResponse<PublicEstimatePayload>(response);
}

export function getPublicEstimateActionError(error: unknown) {
  if (error instanceof PublicEstimateError) {
    return error.message;
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Unable to process the estimate right now.";
}
