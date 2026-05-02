import { apiFetch, apiUpload } from "@/lib/auth";

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

export async function createIssueReportToken(bookingId: number) {
  return apiFetch<IssueReportTokenResponse>(`bookings/${bookingId}/issue-report-token/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function fetchPublicIssueReport(token: string) {
  return apiFetch<PublicIssueReportContext>(`public/issue-report/${token}/`);
}

export async function submitPublicIssueReport(token: string, formData: FormData) {
  return apiUpload<PublicIssueReportResponse>(`public/issue-report/${token}/`, formData);
}
