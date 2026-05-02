import { apiFetch } from "@/lib/auth";
import type { BillingSummary } from "@/lib/dashboard";
import type { Campaign } from "@/lib/campaigns";

type Paginated<T> = {
  results: T[];
};

export type InvoiceLine = {
  id: number;
  invoice: number;
  booking: number | null;
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
  finalized_at: string | null;
  lines: CampaignEstimateLine[];
};

export type BillingPayload = {
  estimates: CampaignEstimate[];
  invoices: Invoice[];
  campaigns: Campaign[];
  summary: BillingSummary;
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
