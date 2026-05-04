import { ApiError, apiFetch } from "@/lib/auth";
import type { BillingSummary } from "@/lib/dashboard";
import type { Campaign } from "@/lib/campaigns";

type Paginated<T> = {
  results: T[];
};

export type InvoiceLine = {
  id: number;
  invoice: number;
  booking: number | null;
  site_name: string;
  media_unit_label: string;
  booking_start_date: string | null;
  booking_end_date: string | null;
  media_cost: string;
  flex_cost: string;
  installation_cost: string;
  other_cost: string;
  cost_notes: string;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
};

export type Payment = {
  id: number;
  invoice: number;
  payment_date: string;
  amount: string;
  method: string;
  reference_number: string;
};

export type Invoice = {
  id: number;
  campaign: number;
  invoice_number: string | null;
  issue_date: string | null;
  due_date: string | null;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  status: string;
  lines: InvoiceLine[];
  payments: Payment[];
};

export type CampaignEstimateLine = {
  id: number;
  estimate: number;
  media_unit: number | null;
  media_unit_label: string;
  description: string;
  start_date: string;
  end_date: string;
  quantity: string;
  unit_rate: string;
  tax_rate: string;
  taxable_amount: string;
  tax_amount: string;
  total_amount: string;
};

export type CampaignEstimate = {
  id: number;
  client: number;
  client_name: string;
  campaign: number | null;
  campaign_name?: string;
  estimate_number: string | null;
  title: string;
  start_date: string;
  end_date: string;
  status: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  notes: string;
  shared_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  public_path?: string | null;
  lines: CampaignEstimateLine[];
};

export type BillingPayload = {
  estimates: CampaignEstimate[];
  invoices: Invoice[];
  campaigns: Campaign[];
  summary: BillingSummary;
};

export type CampaignEstimateCreateInput = {
  client: number;
  campaign: number | null;
  title: string;
  start_date: string;
  end_date: string;
  notes: string;
};

export type CampaignEstimateLineCreateInput = {
  estimate: number;
  media_unit: number | null;
  description: string;
  start_date: string;
  end_date: string;
  quantity: string;
  unit_rate: string;
  tax_rate: string;
};

export type CampaignInvoicePreviewLine = {
  booking_id: number;
  line_number: number;
  site_name: string;
  media_unit_label: string;
  start_date: string;
  end_date: string;
  media_cost: string;
  flex_cost: string;
  installation_cost: string;
  other_cost: string;
  cost_notes: string;
  line_total: string;
  description: string;
};

export type CampaignInvoicePreview = {
  campaign_id: number;
  campaign_name: string;
  campaign_code: string;
  client_name: string;
  start_date: string;
  end_date: string;
  confirmed_booking_count: number;
  subtotal: string;
  total_amount: string;
  existing_invoice_id: number | null;
  existing_invoice_number: string | null;
  can_generate: boolean;
  message: string;
  lines: CampaignInvoicePreviewLine[];
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchBillingData(): Promise<BillingPayload> {
  const [estimates, invoices, campaigns, summary] = await Promise.all([
    list<CampaignEstimate>("billing/campaign-estimates/"),
    list<Invoice>("billing/invoices/"),
    list<Campaign>("campaigns/"),
    apiFetch<BillingSummary>("billing/invoices/summary/"),
  ]);
  return { estimates, invoices, campaigns, summary };
}

export async function fetchCampaignInvoicePreview(campaignId: number) {
  return apiFetch<CampaignInvoicePreview>(`campaigns/${campaignId}/invoice-preview/`);
}

export async function generateCampaignInvoice(campaignId: number) {
  return apiFetch<Invoice>(`campaigns/${campaignId}/generate-invoice/`, {
    method: "POST",
  });
}

export async function createCampaignEstimate(payload: CampaignEstimateCreateInput) {
  return apiFetch<CampaignEstimate>("billing/campaign-estimates/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createCampaignEstimateLine(payload: CampaignEstimateLineCreateInput) {
  return apiFetch<CampaignEstimateLine>("billing/campaign-estimate-lines/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function shareCampaignEstimate(estimateId: number) {
  return apiFetch<CampaignEstimate>(`billing/campaign-estimates/${estimateId}/share/`, {
    method: "POST",
  });
}

export async function approveCampaignEstimate(estimateId: number) {
  return apiFetch<CampaignEstimate>(`billing/campaign-estimates/${estimateId}/approve/`, {
    method: "POST",
  });
}

export async function rejectCampaignEstimate(estimateId: number) {
  return apiFetch<CampaignEstimate>(`billing/campaign-estimates/${estimateId}/reject/`, {
    method: "POST",
  });
}

export function getInvoiceActionError(error: unknown) {
  if (error instanceof ApiError) {
    const fieldMessage = Object.values(error.fieldErrors).flat()[0];
    return fieldMessage || error.message;
  }
  return error instanceof Error ? error.message : "Unable to generate invoice.";
}
