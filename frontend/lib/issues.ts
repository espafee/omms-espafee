import { ApiError, apiFetch } from "@/lib/auth";

const API_ROOT = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";

function normalizeUrl(root: string, path: string) {
  return `${root.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

export type IssueReportTokenResponse = {
  token: string;
  expires_at: string;
  public_url: string;
};

export type PublicIssueReportContext = {
  campaign_name: string;
  site_name: string;
  unit_name: string;
  location: string;
  booking_start: string;
  booking_end: string;
  expires_at: string;
};

export type PublicIssueReportResponse = {
  detail: string;
  issue_id: number;
  priority: string;
  sla_status: string;
};

export class PublicIssueReportError extends Error {
  status: number;
  code: string;

  constructor(message: string, status = 0, code = "request_failed") {
    super(message);
    this.name = "PublicIssueReportError";
    this.status = status;
    this.code = code;
  }
}

async function parsePublicIssueResponse<T>(response: Response): Promise<T> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    if (payload && typeof payload === "object" && "detail" in payload) {
      const errorPayload = payload as { detail: unknown; code?: unknown };
      throw new PublicIssueReportError(
        String(errorPayload.detail),
        response.status,
        errorPayload.code ? String(errorPayload.code) : "request_failed",
      );
    }
    throw new PublicIssueReportError("This issue reporting link is not available right now.", response.status);
  }

  return payload as T;
}

export async function createIssueReportToken(bookingId: number) {
  return apiFetch<IssueReportTokenResponse>(`bookings/${bookingId}/issue-report-token/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function fetchPublicIssueReport(token: string) {
  let response: Response;
  try {
    response = await fetch(normalizeUrl(API_ROOT, `public/issue-report/${token}/`), { cache: "no-store" });
  } catch {
    throw new PublicIssueReportError(
      "We couldn't reach the server for this issue reporting link. Please try again.",
      0,
      "network_error",
    );
  }
  return parsePublicIssueResponse<PublicIssueReportContext>(response);
}

export async function submitPublicIssueReport(token: string, formData: FormData) {
  let response: Response;
  try {
    response = await fetch(normalizeUrl(API_ROOT, `public/issue-report/${token}/`), {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new PublicIssueReportError(
      "We couldn't reach the server for this issue reporting link. Please try again.",
      0,
      "network_error",
    );
  }
  return parsePublicIssueResponse<PublicIssueReportResponse>(response);
}

export function getPublicIssueReportError(error: unknown) {
  if (error instanceof PublicIssueReportError) {
    return error.message;
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return error instanceof Error ? error.message : "Unable to submit this issue report right now.";
}
