import { ApiError, apiFetch } from "@/lib/auth";
import type { BookingSummary } from "@/lib/dashboard";
import type { Campaign } from "@/lib/campaigns";
import type { InventorySite, InventoryUnit } from "@/lib/inventory";

type Paginated<T> = {
  results: T[];
};

export type Booking = {
  id: number;
  campaign: number;
  media_unit: number;
  start_date: string;
  end_date: string;
  booked_rate: string;
  status: string;
  remarks: string;
  created_at: string;
  updated_at: string;
};

export type BookingCreateInput = {
  campaign: number;
  media_unit: number;
  start_date: string;
  end_date: string;
  booked_rate: string;
  status: string;
  remarks: string;
};

export type BookingPayload = {
  bookings: Booking[];
  campaigns: Campaign[];
  sites: InventorySite[];
  units: InventoryUnit[];
  summary: BookingSummary;
};

async function list<T>(path: string) {
  const payload = await apiFetch<Paginated<T> | T[]>(path);
  return Array.isArray(payload) ? payload : payload.results;
}

export function getBookingCreateError(error: unknown) {
  if (error instanceof ApiError) {
    return { message: error.message, fieldErrors: error.fieldErrors };
  }
  return {
    message: error instanceof Error ? error.message : "Unable to create booking.",
    fieldErrors: {},
  };
}

export async function fetchBookingsData(): Promise<BookingPayload> {
  const [bookings, campaigns, sites, units, summary] = await Promise.all([
    list<Booking>("bookings/"),
    list<Campaign>("campaigns/"),
    list<InventorySite>("inventory/sites/"),
    list<InventoryUnit>("inventory/units/"),
    apiFetch<BookingSummary>("bookings/summary/"),
  ]);
  return { bookings, campaigns, sites, units, summary };
}

export async function createBooking(payload: BookingCreateInput) {
  return apiFetch<Booking>("bookings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
