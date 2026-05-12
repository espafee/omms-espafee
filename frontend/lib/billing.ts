import { ApiError, apiFetch, getAccessToken, parseApiError } from "@/lib/auth";
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
  payment_mode: string;
  reference_number: string;
  notes: string;
  recorded_by: number | null;
  recorded_by_name: string;
  created_at: string;
};

export type CreditNote = {
  id: number;
  invoice: number;
  credit_date: string;
  amount: string;
  method: string;
  credit_method: string;
  reference_number: string;
  reason: string;
  notes: string;
  created_by: number | null;
  created_by_name: string;
  created_at: string;
};

export type InvoiceEvent = {
  id: number;
  invoice: number;
  event_type: string;
  actor: number | null;
  actor_name: string;
  from_status: string;
  to_status: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
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
  cancellation_reason?: string;
  invoice_total: string;
  amount_paid: string;
  balance_due: string;
  payment_status: string;
  pdf_file?: string | null;
  lines: InvoiceLine[];
  payments: Payment[];
  credit_notes: CreditNote[];
  events: InvoiceEvent[];
};

export type ClientStatement = {
  client_id: number;
  client_name: string;
  total_billed: string;
  total_paid: string;
  outstanding_balance: string;
  unpaid_invoices: Invoice[];
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
  client_response_comment?: string;
  public_path?: string | null;
  lines: CampaignEstimateLine[];
};

export type BillingPayload = {
  estimates: CampaignEstimate[];
  invoices: Invoice[];
  campaigns: Campaign[];
  summary: BillingSummary;
};

export type InvoicePaymentCreateInput = {
  amount: string;
  payment_date: string;
  payment_mode: string;
  reference_number: string;
  notes: string;
};

export type InvoiceCancelInput = {
  reason: string;
  credit_amount?: string;
  credit_date?: string;
  credit_method?: string;
  credit_reference_number?: string;
  credit_notes?: string;
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
    apiFetch<BillingSummary>("billing/summary/"),
  ]);
  return { estimates, invoices, campaigns, summary };
}

export async function fetchInvoice(invoiceId: number) {
  return apiFetch<Invoice>(`billing/invoices/${invoiceId}/`);
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

export async function createInvoicePayment(invoiceId: number, payload: InvoicePaymentCreateInput) {
  return apiFetch<Payment>(`billing/invoices/${invoiceId}/payments/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function cancelInvoice(invoiceId: number, payload: InvoiceCancelInput) {
  return apiFetch<Invoice>(`billing/invoices/${invoiceId}/cancel/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchClientStatement(clientId: number) {
  return apiFetch<ClientStatement>(`billing/invoices/client-statement/?client=${clientId}`);
}

async function downloadBillingBlob(path: string, fallbackFilename: string) {
  const token = getAccessToken();
  const apiRoot = process.env.NEXT_PUBLIC_API_ROOT ?? "http://127.0.0.1:8000/api/v1";
  const response = await fetch(normalizeUrl(apiRoot, path), {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  return {
    blob: await response.blob(),
    filename: getFilenameFromDisposition(response.headers.get("content-disposition")) ?? fallbackFilename,
  };
}

export async function exportClientStatementCsv(clientId: number) {
  return downloadBillingBlob(
    `billing/invoices/client-statement/export-csv/?client=${clientId}`,
    `client-statement-${clientId}.csv`,
  );
}

export async function exportClientStatementPdf(clientId: number) {
  return downloadBillingBlob(
    `billing/invoices/client-statement/export-pdf/?client=${clientId}`,
    `client-statement-${clientId}.pdf`,
  );
}

export async function generateInvoicePdf(invoiceId: number) {
  return apiFetch<Invoice>(`billing/invoices/${invoiceId}/generate-pdf/`, {
    method: "POST",
  });
}

export async function fetchInvoicePdfLink(invoiceId: number) {
  return apiFetch<{ url: string; expires_in: number }>(`billing/invoices/${invoiceId}/pdf-link/`);
}

export async function issueInvoice(invoiceId: number) {
  return apiFetch<Invoice>(`billing/invoices/${invoiceId}/issue/`, {
    method: "POST",
  });
}

function normalizeUrl(root: string, path: string) {
  return `${root.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

function getFilenameFromDisposition(contentDisposition: string | null) {
  if (!contentDisposition) {
    return null;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const basicMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  return basicMatch?.[1] ?? null;
}

export async function downloadInvoicePdf(invoiceId: number) {
  return downloadBillingBlob(`billing/invoices/${invoiceId}/download-pdf/`, `invoice-${invoiceId}.pdf`);
}

export function getInvoiceActionError(error: unknown) {
  if (error instanceof ApiError) {
    const fieldMessage = Object.values(error.fieldErrors).flat()[0];
    return fieldMessage || error.message;
  }
  return error instanceof Error ? error.message : "Unable to generate invoice.";
}
