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
  invoice_number: string;
  issue_date: string;
  due_date: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  status: string;
  lines: InvoiceLine[];
  payments: Payment[];
};

export type BillingPayload = {
  invoices: Invoice[];
  campaigns: Campaign[];
  summary: BillingSummary;
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export async function fetchBillingData(): Promise<BillingPayload> {
  const [invoices, campaigns, summary] = await Promise.all([
    list<Invoice>("billing/invoices/"),
    list<Campaign>("campaigns/"),
    apiFetch<BillingSummary>("billing/invoices/summary/"),
  ]);
  return { invoices, campaigns, summary };
}
