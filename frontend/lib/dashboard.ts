import { apiFetch } from "@/lib/auth";

export type CampaignSummary = {
  total_campaigns: number;
  active_campaigns: number;
  draft_campaigns: number;
  completed_campaigns: number;
  total_budget: string;
  active_budget: string;
  total_bookings: number;
  live_bookings: number;
  approved_assets: number;
};

export type BookingSummary = {
  total_bookings: number;
  pending_bookings: number;
  confirmed_bookings: number;
  live_bookings: number;
  completed_bookings: number;
  cancelled_bookings: number;
  unique_media_units: number;
  total_booked_value: string;
  live_booked_value: string;
};

export type BillingSummary = {
  total_estimated: string;
  total_approved_estimates: string;
  total_invoices: number;
  issued_invoices: number;
  overdue_invoices: number;
  paid_invoices: number;
  partially_paid_invoices: number;
  payment_count: number;
  total_invoiced: string;
  overdue_amount: string;
  total_paid: string;
  total_collected: string;
  outstanding_amount: string;
  outstanding_balance: string;
};

export type DashboardPayload = {
  campaigns: CampaignSummary;
  bookings: BookingSummary;
  billing: BillingSummary;
};

export function formatCurrency(value: string | number | null | undefined) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(amount) ? amount : 0);
}

export async function fetchDashboardData(): Promise<DashboardPayload> {
  const [campaigns, bookings, billing] = await Promise.all([
    apiFetch<CampaignSummary>("campaigns/summary/"),
    apiFetch<BookingSummary>("bookings/summary/"),
    apiFetch<BillingSummary>("billing/invoices/summary/"),
  ]);

  return {
    campaigns,
    bookings,
    billing,
  };
}
