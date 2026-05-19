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
  ending_soon_count: number;
  campaigns_at_risk: number;
  campaigns_poe_risk: number;
  campaigns_billing_risk: number;
  critical_campaigns: number;
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
  draft_invoices: number;
  issued_invoices: number;
  due_soon_invoices: number;
  overdue_invoices: number;
  paid_invoices: number;
  partially_paid_invoices: number;
  payment_count: number;
  total_invoiced: string;
  overdue_amount: string;
  total_paid: string;
  payments_received_this_month: string;
  total_collected: string;
  outstanding_amount: string;
  outstanding_balance: string;
  collection_efficiency_percentage: number;
  average_days_to_payment: number | null;
  overdue_age_buckets: Array<{ bucket: string; label: string; count: number; amount: string }>;
  top_overdue_clients: Array<{ client: string; count: number; amount: string; oldest_days_overdue: number }>;
  payment_trend: Array<{ day: string; amount: string; payments: number }>;
};

export type DashboardPayload = {
  campaigns: CampaignSummary;
  bookings: BookingSummary;
  billing: BillingSummary | null;
};

export type DashboardWidget = {
  key: string;
  label: string;
  category: string;
  description: string;
  href: string;
  is_visible: boolean;
  is_required: boolean;
  sort_order: number;
};

export type DashboardProfile = {
  role: string;
  role_label: string;
  active_widgets: string[];
  available_widgets: DashboardWidget[];
  hidden_widgets: string[];
  can_customize: boolean;
  can_view_finance: boolean;
  can_view_operations: boolean;
};

export function formatCurrency(value: string | number | null | undefined) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(amount) ? amount : 0);
}

export async function fetchDashboardProfile(): Promise<DashboardProfile> {
  return apiFetch<DashboardProfile>("observability/dashboard-profile/");
}

export async function updateDashboardProfile(widgets: Array<{ widget_key: string; is_visible: boolean; sort_order: number }>) {
  return apiFetch<DashboardProfile>("observability/dashboard-profile/", {
    method: "PATCH",
    body: JSON.stringify({ widgets }),
  });
}

export async function restoreDashboardProfileDefaults() {
  return apiFetch<DashboardProfile>("observability/dashboard-profile/", {
    method: "POST",
    body: JSON.stringify({ action: "restore_defaults" }),
  });
}

export async function fetchDashboardData(options: { includeBilling?: boolean } = {}): Promise<DashboardPayload> {
  const [campaigns, bookings, billing] = await Promise.all([
    apiFetch<CampaignSummary>("campaigns/summary/"),
    apiFetch<BookingSummary>("bookings/summary/"),
    options.includeBilling ? apiFetch<BillingSummary>("billing/invoices/summary/") : Promise.resolve(null),
  ]);

  return {
    campaigns,
    bookings,
    billing,
  };
}
