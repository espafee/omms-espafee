"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { clearAuthSession, fetchCurrentUser, getAccessToken, getStoredUser } from "@/lib/auth";
import { BookingCreatePanel, type BookingFormState } from "@/components/booking-create-panel";
import { createBooking, fetchBookingsData, getBookingCreateError, type BookingPayload } from "@/lib/bookings";
import { formatCurrency } from "@/lib/dashboard";
import { formatMediaUnitSiteType, type InventoryUnit } from "@/lib/inventory";

type StoredUser = {
  id?: number;
  email?: string;
  role?: string;
};

const WRITE_ROLES = new Set(["admin", "sales"]);

const INITIAL_FORM: BookingFormState = {
  campaign: 0,
  site: 0,
  media_unit: 0,
  start_date: "",
  end_date: "",
  booked_rate: "",
  status: "pending",
  remarks: "",
};

function formatDateRange(startDate: string, endDate: string) {
  const formatter = new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return `${formatter.format(new Date(startDate))} - ${formatter.format(new Date(endDate))}`;
}

export default function BookingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<StoredUser | null>(null);
  const [bookingData, setBookingData] = useState<BookingPayload | null>(null);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [form, setForm] = useState<BookingFormState>(INITIAL_FORM);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canManageBookings = WRITE_ROLES.has(user?.role ?? "");

  function getUnitById(unitId: number): InventoryUnit | undefined {
    return bookingData?.units.find((unit) => unit.id === unitId);
  }

  function getUnitsForSite(siteId: number): InventoryUnit[] {
    return (bookingData?.units ?? []).filter((unit) => unit.site === siteId);
  }

  function hydrateBookingForm(payload: BookingPayload, profile?: StoredUser | null) {
    const firstCampaign = payload.campaigns[0];
    const firstSite = payload.sites[0];
    const firstUnit = firstSite ? payload.units.find((unit) => unit.site === firstSite.id) : undefined;

    setForm((current) => ({
      ...current,
      campaign: current.campaign || firstCampaign?.id || 0,
      site: current.site || firstSite?.id || 0,
      media_unit: current.media_unit || firstUnit?.id || 0,
      booked_rate: current.booked_rate || firstUnit?.monthly_rate || "",
      status: current.status || "pending",
    }));

    if (profile) {
      setUser(profile);
    }
  }

  async function loadBookings(profileHint?: StoredUser | null) {
    setIsLoading(true);
    setError("");

    try {
      const profile = profileHint ?? (await fetchCurrentUser());
      if (profile) {
        setUser(profile);
      }

      const payload = await fetchBookingsData();
      setBookingData(payload);
      hydrateBookingForm(payload, profile);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load bookings.";
      setError(message);
      if (message.includes("sign in again")) {
        router.replace("/login");
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
    }
    void loadBookings(storedUser);
  }, [router]);

  function handleLogout() {
    clearAuthSession();
    router.replace("/login");
  }

  function updateForm<K extends keyof BookingFormState>(field: K, value: BookingFormState[K]) {
    setFormError("");
    setFormSuccess("");
    setFieldErrors({});

    if (field === "site") {
      const siteId = Number(value);
      const siteUnits = getUnitsForSite(siteId);
      const nextUnit = siteUnits[0];
      setForm((current) => ({
        ...current,
        site: siteId,
        media_unit: nextUnit?.id || 0,
        booked_rate: nextUnit?.monthly_rate || "",
      }));
      return;
    }

    if (field === "media_unit") {
      const unitId = Number(value);
      const unit = getUnitById(unitId);
      setForm((current) => ({
        ...current,
        media_unit: unitId,
        booked_rate: unit?.monthly_rate || current.booked_rate,
      }));
      return;
    }

    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleCreateBooking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setFormError("");
    setFormSuccess("");
    setFieldErrors({});
    setIsSubmitting(true);

    try {
      await createBooking({
        campaign: form.campaign,
        media_unit: form.media_unit,
        start_date: form.start_date,
        end_date: form.end_date,
        booked_rate: Number(form.booked_rate).toFixed(2),
        status: form.status,
        remarks: form.remarks,
      });

      setFormSuccess("Booking created successfully.");
      setForm((current) => ({
        ...INITIAL_FORM,
        campaign: current.campaign,
        site: current.site,
        media_unit: current.media_unit,
        booked_rate: current.booked_rate,
      }));
      await loadBookings(user);
    } catch (submitError) {
      const normalized = getBookingCreateError(submitError);
      setFormError(normalized.message);
      setFieldErrors(normalized.fieldErrors);
    } finally {
      setIsSubmitting(false);
    }
  }

  const campaignMap = useMemo(() => {
    const map = new Map<number, { code: string; name: string }>();
    for (const campaign of bookingData?.campaigns ?? []) {
      map.set(campaign.id, { code: campaign.code, name: campaign.name });
    }
    return map;
  }, [bookingData]);

  const siteMap = useMemo(() => {
    const map = new Map<number, string>();
    for (const site of bookingData?.sites ?? []) {
      map.set(site.id, site.name);
    }
    return map;
  }, [bookingData]);

  const unitMap = useMemo(() => {
    const map = new Map<number, { code: string; siteId: number; status: string; facingDirection: string; siteType: string }>();
    for (const unit of bookingData?.units ?? []) {
      map.set(unit.id, {
        code: unit.unit_code,
        siteId: unit.site,
        status: unit.status,
        facingDirection: unit.facing_direction,
        siteType: unit.site_type,
      });
    }
    return map;
  }, [bookingData]);

  const quickStats = useMemo(() => {
    if (!bookingData) {
      return [];
    }

    return [
      { label: "Total bookings", value: String(bookingData.summary.total_bookings) },
      { label: "Live bookings", value: String(bookingData.summary.live_bookings) },
      { label: "Confirmed bookings", value: String(bookingData.summary.confirmed_bookings) },
      { label: "Active units", value: String(bookingData.summary.unique_media_units) },
    ];
  }, [bookingData]);

  const statusCards = useMemo(() => {
    return [
      { label: "Pending", value: bookingData?.summary.pending_bookings ?? 0 },
      { label: "Confirmed", value: bookingData?.summary.confirmed_bookings ?? 0 },
      { label: "Live", value: bookingData?.summary.live_bookings ?? 0 },
      { label: "Completed", value: bookingData?.summary.completed_bookings ?? 0 },
    ];
  }, [bookingData]);

  const selectedSite = useMemo(
    () => bookingData?.sites.find((site) => site.id === form.site) ?? null,
    [bookingData, form.site],
  );

  const selectedUnit = useMemo(
    () => bookingData?.units.find((unit) => unit.id === form.media_unit) ?? null,
    [bookingData, form.media_unit],
  );

  const unitSpotlight = useMemo(() => {
    const totals = new Map<number, number>();
    for (const booking of bookingData?.bookings ?? []) {
      totals.set(booking.media_unit, (totals.get(booking.media_unit) ?? 0) + 1);
    }

    return Array.from(totals.entries())
      .map(([unitId, count]) => {
        const unit = unitMap.get(unitId);
        return {
          unitId,
          count,
          code: unit?.code ?? `Unit #${unitId}`,
          siteName: unit ? siteMap.get(unit.siteId) ?? "Unassigned site" : "Unassigned site",
          status: unit?.status ?? "unknown",
          facingDirection: unit?.facingDirection ?? "",
          siteType: unit?.siteType ?? "",
        };
      })
      .sort((left, right) => right.count - left.count)
      .slice(0, 5);
  }, [bookingData, siteMap, unitMap]);

  return (
    <AppShell
      active="bookings"
      roleLabel={user?.role ?? "Authenticated"}
      userEmail={user?.email ?? "Loading user..."}
      title="Booking board"
      eyebrow="Bookings"
      description="Monitor live placement windows, booked revenue, and unit utilization across every campaign scope available to your account."
      onLogout={handleLogout}
    >
      {error ? <p className="error dashboard-error">{error}</p> : null}

      {canManageBookings ? (
        <BookingCreatePanel
          campaigns={bookingData?.campaigns ?? []}
          sites={bookingData?.sites ?? []}
          units={bookingData?.units ?? []}
          selectedSite={selectedSite}
          selectedUnit={selectedUnit}
          form={form}
          fieldErrors={fieldErrors}
          formError={formError}
          formSuccess={formSuccess}
          isLoading={isLoading}
          isSubmitting={isSubmitting}
          onSubmit={handleCreateBooking}
          onChange={updateForm}
        />
      ) : null}

      <section className="summary-row" aria-label="Booking stats">
        {quickStats.map((item) => (
          <article className="summary-card" key={item.label}>
            <p className="stat-label">{item.label}</p>
            <p className="summary-value">{isLoading ? "..." : item.value}</p>
          </article>
        ))}
      </section>

      <section className="module-grid">
        <article className="module-card">
          <div className="module-head">
            <h2>Revenue pipeline</h2>
            <span>Finance</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Total booked value</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(bookingData?.summary.total_booked_value ?? "0.00")}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Live booked value</p>
              <p className="stat-value">
                {isLoading ? "..." : formatCurrency(bookingData?.summary.live_booked_value ?? "0.00")}
              </p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Unique units</p>
              <p className="stat-value">{isLoading ? "..." : bookingData?.summary.unique_media_units ?? 0}</p>
            </div>
          </div>
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Status mix</h2>
            <span>Delivery</span>
          </div>
          <div className="module-stats">
            {statusCards.map((item) => (
              <div className="module-stat" key={item.label}>
                <p className="stat-label">{item.label}</p>
                <p className="stat-value">{isLoading ? "..." : item.value}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="module-card module-card-highlight">
          <div className="module-head">
            <h2>Scheduling note</h2>
            <span>Operations</span>
          </div>
          <div className="module-stats">
            <div className="module-stat">
              <p className="stat-label">Overlap protection</p>
              <p className="stat-value">Enabled</p>
            </div>
            <div className="module-stat">
              <p className="stat-label">Validation rule</p>
              <p className="table-wrap">
                Booking creation already prevents confirmed or live overlaps on the same unit and date window.
              </p>
            </div>
          </div>
        </article>
      </section>

      <section className="bookings-layout">
        <article className="module-card module-card-wide">
          <div className="module-head">
            <h2>Booking roster</h2>
            <span>{bookingData?.bookings.length ?? 0} items</span>
          </div>
          <div className="inventory-table-wrap">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Media unit</th>
                  <th>Timeline</th>
                  <th>Status</th>
                  <th>Booked rate</th>
                  <th>Remarks</th>
                  <th>Field</th>
                </tr>
              </thead>
              <tbody>
                {(bookingData?.bookings ?? []).map((booking) => {
                  const campaign = campaignMap.get(booking.campaign);
                  const unit = unitMap.get(booking.media_unit);
                  const siteName = unit ? siteMap.get(unit.siteId) ?? "Unassigned site" : "Unassigned site";

                  return (
                    <tr key={booking.id}>
                      <td>
                        <div className="table-primary">
                          <strong>{campaign?.name ?? `Campaign #${booking.campaign}`}</strong>
                          <span>{campaign?.code ?? "Unknown code"}</span>
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">
                          <strong>{unit?.code ?? `Unit #${booking.media_unit}`}</strong>
                          <span>
                            {siteName}
                            {unit?.facingDirection ? ` • ${unit.facingDirection}` : ""}
                            {unit?.siteType ? ` • ${formatMediaUnitSiteType(unit.siteType)}` : ""}
                          </span>
                        </div>
                      </td>
                      <td>{formatDateRange(booking.start_date, booking.end_date)}</td>
                      <td>
                        <span className={`status-pill status-${booking.status}`}>{booking.status}</span>
                      </td>
                      <td>{formatCurrency(booking.booked_rate)}</td>
                      <td className="table-wrap">{booking.remarks || "No remarks added yet."}</td>
                      <td>
                        <Link className="asset-link" href={`/poe/capture?booking=${booking.id}`}>
                          Capture proof
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!isLoading && (bookingData?.bookings.length ?? 0) === 0 ? (
            <p className="empty-state">No bookings are visible for the current account.</p>
          ) : null}
        </article>

        <article className="module-card">
          <div className="module-head">
            <h2>Unit spotlight</h2>
            <span>Inventory</span>
          </div>
          <div className="asset-list">
            {unitSpotlight.map((unit) => (
              <article className="asset-card" key={unit.unitId}>
                <div className="asset-head">
                  <div>
                    <p className="site-code">{unit.code}</p>
                    <h3>{unit.siteName}</h3>
                  </div>
                  <span className={`status-pill status-${unit.status}`}>{unit.status}</span>
                </div>
                <p className="site-copy">
                  {unit.count} booking window(s) attached
                  {unit.facingDirection ? ` • ${unit.facingDirection}` : ""}
                  {unit.siteType ? ` • ${formatMediaUnitSiteType(unit.siteType)}` : ""}
                </p>
              </article>
            ))}
            {!isLoading && unitSpotlight.length === 0 ? (
              <p className="empty-state">No booked media units are available for the current scope.</p>
            ) : null}
          </div>
        </article>
      </section>
    </AppShell>
  );
}
