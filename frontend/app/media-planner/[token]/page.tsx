"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { ImageLightbox } from "@/components/image-lightbox";
import {
  fetchPublicPlanner,
  submitPublicProposal,
  type PublicPlannerPayload,
  type PublicPlannerUnit,
} from "@/lib/planner";

type Filters = {
  search: string;
  city: string;
  location: string;
  availability: string;
  display_format: string;
  facing: string;
  illumination: string;
  width: string;
  height: string;
  min_price: string;
  max_price: string;
};
const EMPTY_FILTERS: Filters = {
  search: "",
  city: "",
  location: "",
  availability: "",
  display_format: "",
  facing: "",
  illumination: "",
  width: "",
  height: "",
  min_price: "",
  max_price: "",
};

export default function PublicMediaPlannerPage() {
  const { token } = useParams<{ token: string }>();
  const [payload, setPayload] = useState<PublicPlannerPayload | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [viewer, setViewer] = useState<PublicPlannerUnit | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [showProposal, setShowProposal] = useState(false);
  const [reference, setReference] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const storageKey = useMemo(
    () => `omms-planner-basket:${token.slice(0, 18)}`,
    [token],
  );
  useEffect(() => {
    try {
      setSelected(JSON.parse(sessionStorage.getItem(storageKey) || "[]"));
    } catch {
      setSelected([]);
    }
  }, [storageKey]);
  useEffect(() => {
    sessionStorage.setItem(storageKey, JSON.stringify(selected));
  }, [selected, storageKey]);

  const load = useCallback(async () => {
    if (!token) return;
    setIsLoading(true);
    setError("");
    try {
      setPayload(
        await fetchPublicPlanner(token, {
          ...filters,
          start_date: startDate,
          end_date: endDate,
          page_size: 48,
        }),
      );
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "This media planner is unavailable.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [endDate, filters, startDate, token]);
  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timeout);
  }, [load]);

  const unitsById = useMemo(
    () =>
      new Map((payload?.results ?? []).map((unit) => [unit.public_id, unit])),
    [payload],
  );
  const selectedUnits = selected
    .map((id) => unitsById.get(id))
    .filter((unit): unit is PublicPlannerUnit => Boolean(unit));
  const subtotal = selectedUnits.reduce(
    (total, unit) => total + Number(unit.monthly_rate || 0),
    0,
  );
  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id)
        ? current.filter((value) => value !== id)
        : [...current, id],
    );
  const clearFilters = () => setFilters(EMPTY_FILTERS);
  const hasActiveFilters = Object.values(filters).some(Boolean);
  const emptyState = getEmptyState({
    isLoading,
    eligibleCount: payload?.meta?.eligible_unit_count ?? 0,
    resultCount: payload?.count ?? 0,
    hasActiveFilters,
    hasDates: Boolean(startDate && endDate),
    availability: filters.availability,
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!startDate || !endDate || !selected.length) {
      setError("Select campaign dates and at least one advertising unit.");
      return;
    }
    setIsSubmitting(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const result = await submitPublicProposal(token, {
        campaign_name: form.get("campaign_name"),
        brand_company: form.get("brand_company"),
        objective: form.get("objective"),
        requested_start_date: startDate,
        requested_end_date: endDate,
        contact_name: form.get("contact_name"),
        contact_email: form.get("contact_email"),
        contact_phone: form.get("contact_phone"),
        billing_gstin: form.get("billing_gstin"),
        billing_details: form.get("billing_details"),
        notes: form.get("notes"),
        unit_public_ids: selected,
        idempotency_key: crypto.randomUUID(),
      });
      setReference(result.reference);
      setSelected([]);
      setShowProposal(false);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Proposal submission failed.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (error && !payload)
    return (
      <main className="planner-public-shell">
        <section className="planner-public-state">
          <p className="site-code">LIVE MEDIA PLANNER</p>
          <h1>Unable to load media units</h1>
          <p>{error}</p>
          <button className="submit" type="button" onClick={() => void load()}>
            Retry
          </button>
        </section>
      </main>
    );
  return (
    <main className="planner-public-shell">
      <header className="planner-public-header">
        <div>
          <p className="site-code">{payload?.planner.tenant_name || "OMMS"}</p>
          <h1>{payload?.planner.title || "Live Media Planner"}</h1>
          <p>
            Plan outdoor media with current inventory availability and submit
            selections for formal review.
          </p>
        </div>
        <div className="planner-header-meta">
          {payload?.planner.client_name ? (
            <strong>Prepared for {payload.planner.client_name}</strong>
          ) : null}
          <span>
            {payload?.planner.expires_at
              ? `Available until ${new Date(payload.planner.expires_at).toLocaleDateString()}`
              : "Secure client workspace"}
          </span>
          {payload?.planner.contact_email ? (
            <a href={`mailto:${payload.planner.contact_email}`}>
              {payload.planner.contact_email}
            </a>
          ) : null}
        </div>
      </header>

      <section className="planner-date-bar" aria-label="Campaign dates">
        <div>
          <p className="site-code">CAMPAIGN WINDOW</p>
          <strong>Check live availability</strong>
        </div>
        <label>
          <span>Start date</span>
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label>
          <span>End date</span>
          <input
            type="date"
            min={startDate}
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>
        <span className="planner-live-indicator">Live availability</span>
      </section>

      <details className="planner-filter-panel" open>
        <summary>Find advertising units</summary>
        <div className="planner-filter-grid">
          <label>
            <span>Search</span>
            <input
              value={filters.search}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  search: event.target.value,
                }))
              }
              placeholder="Unit, location, city"
            />
          </label>
          <label>
            <span>City</span>
            <select
              value={filters.city}
              onChange={(event) =>
                setFilters((value) => ({ ...value, city: event.target.value }))
              }
            >
              <option value="">All cities</option>
              {(payload?.filters.cities ?? []).map((city) => (
                <option key={city}>{city}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Location</span>
            <select
              value={filters.location}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  location: event.target.value,
                }))
              }
            >
              <option value="">All locations</option>
              {(payload?.filters.locations ?? []).map((location) => (
                <option key={location}>{location}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Availability</span>
            <select
              value={filters.availability}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  availability: event.target.value,
                }))
              }
            >
              <option value="">All availability</option>
              {[
                "available",
                "partially_available",
                "booked",
                "on_hold",
                "under_maintenance",
                "unavailable",
              ].map((value) => (
                <option key={value} value={value}>
                  {formatFacetLabel(value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Format</span>
            <select
              value={filters.display_format}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  display_format: event.target.value,
                }))
              }
            >
              <option value="">All formats</option>
              {(payload?.filters.formats ?? ["single_side", "both_side"]).map(
                (format) => (
                  <option key={format} value={format}>
                    {formatFacetLabel(format)}
                  </option>
                ),
              )}
            </select>
          </label>
          <label>
            <span>Facing</span>
            <select
              value={filters.facing}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  facing: event.target.value,
                }))
              }
            >
              <option value="">All directions</option>
              {(payload?.filters.facing_directions ?? []).map((direction) => (
                <option key={direction} value={direction}>
                  {direction}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Illumination</span>
            <select
              value={filters.illumination}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  illumination: event.target.value,
                }))
              }
            >
              <option value="">Any</option>
              {(payload?.filters.illumination ?? [
                { value: "true", label: "Illuminated" },
                { value: "false", label: "Standard" },
              ]).map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Width</span>
            <input
              type="number"
              min="0"
              value={filters.width}
              onChange={(event) =>
                setFilters((value) => ({ ...value, width: event.target.value }))
              }
            />
          </label>
          <label>
            <span>Height</span>
            <input
              type="number"
              min="0"
              value={filters.height}
              onChange={(event) =>
                setFilters((value) => ({
                  ...value,
                  height: event.target.value,
                }))
              }
            />
          </label>
          {payload?.planner.show_rates ? (
            <>
              <label>
                <span>Minimum rate</span>
                <input
                  type="number"
                  min="0"
                  value={filters.min_price}
                  onChange={(event) =>
                    setFilters((value) => ({
                      ...value,
                      min_price: event.target.value,
                    }))
                  }
                />
              </label>
              <label>
                <span>Maximum rate</span>
                <input
                  type="number"
                  min="0"
                  value={filters.max_price}
                  onChange={(event) =>
                    setFilters((value) => ({
                      ...value,
                      max_price: event.target.value,
                    }))
                  }
                />
              </label>
            </>
          ) : null}
          <button
            className="ghost"
            type="button"
            onClick={clearFilters}
          >
            Clear filters
          </button>
        </div>
      </details>

      {error && payload ? (
        <p className="planner-inline-error" role="alert">
          Unable to load media units. Showing the last available results.{" "}
          <button className="ghost" type="button" onClick={() => void load()}>
            Retry
          </button>
        </p>
      ) : null}
      <section className="planner-results-head">
        <div>
          <p className="site-code">AVAILABLE MEDIA</p>
          <h2>
            {isLoading
              ? "Checking inventory..."
              : `${payload?.count ?? 0} advertising units`}
          </h2>
        </div>
        <p>Availability and pricing are subject to final confirmation.</p>
      </section>
      <section className="planner-unit-grid" aria-busy={isLoading}>
        {isLoading && !payload ? (
          <p className="planner-empty-state">Loading media units...</p>
        ) : null}
        {!isLoading && emptyState ? (
          <div className="planner-empty-state">
            <h2>{emptyState.title}</h2>
            <p>{emptyState.message}</p>
            {emptyState.showClear ? (
              <button className="ghost" type="button" onClick={clearFilters}>
                Clear filters
              </button>
            ) : null}
          </div>
        ) : null}
        {(payload?.results ?? []).map((unit) => {
          const isSelected = selected.includes(unit.public_id);
          return (
            <article className="planner-unit-card" key={unit.public_id}>
              <button
                className="planner-unit-photo"
                type="button"
                onClick={() => setViewer(unit)}
                aria-label={`View photos for ${unit.unit_code}`}
              >
                {unit.primary_photo ? (
                  <img
                    src={unit.primary_photo.url}
                    alt={`${unit.unit_code} at ${unit.location_name}`}
                  />
                ) : (
                  <span>Photo coming soon</span>
                )}
                <span className="planner-photo-count">
                  {unit.photos.length} photo
                  {unit.photos.length === 1 ? "" : "s"}
                </span>
              </button>
              <div className="planner-unit-body">
                <div className="planner-unit-title">
                  <div>
                    <p className="site-code">{unit.city}</p>
                    <h3>{unit.location_name}</h3>
                    <span>{unit.unit_code}</span>
                  </div>
                  <span
                    className={`planner-status status-${unit.availability.status}`}
                  >
                    {unit.availability.label}
                  </span>
                </div>
                <dl className="planner-unit-facts">
                  <div>
                    <dt>Size</dt>
                    <dd>
                      {unit.dimensions.width} x {unit.dimensions.height}
                    </dd>
                  </div>
                  <div>
                    <dt>Facing</dt>
                    <dd>{unit.facing_direction || "Pending"}</dd>
                  </div>
                  <div>
                    <dt>Format</dt>
                    <dd>{unit.display_format.replaceAll("_", " ")}</dd>
                  </div>
                  <div>
                    <dt>Lighting</dt>
                    <dd>{unit.is_illuminated ? "Illuminated" : "Standard"}</dd>
                  </div>
                </dl>
                {unit.description ? <p>{unit.description}</p> : null}
                <div className="planner-unit-actions">
                  <strong>
                    {unit.monthly_rate
                      ? `INR ${Number(unit.monthly_rate).toLocaleString("en-IN")} / month`
                      : "Rate on request"}
                  </strong>
                  <button
                    className={isSelected ? "ghost" : "submit"}
                    type="button"
                    onClick={() => toggle(unit.public_id)}
                  >
                    {isSelected ? "Remove" : "Add to campaign"}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </section>

      <aside
        className="planner-basket-bar"
        aria-label="Campaign proposal basket"
      >
        <div>
          <span>{selected.length} selected</span>
          <strong>
            {payload?.planner.show_rates
              ? `Preliminary INR ${subtotal.toLocaleString("en-IN")}`
              : "Proposal shortlist"}
          </strong>
        </div>
        <button
          className="submit"
          type="button"
          disabled={
            !selected.length || !payload?.planner.allow_proposal_submission
          }
          onClick={() => setShowProposal(true)}
        >
          Request formal estimate
        </button>
      </aside>
      {reference ? (
        <div className="planner-success" role="status">
          <strong>Proposal received</strong>
          <span>
            Reference {reference}. Your selection is awaiting formal
            availability and pricing review.
          </span>
        </div>
      ) : null}

      {viewer ? (
        <ImageLightbox
          images={viewer.photos.map((photo) => ({
            url: photo.url,
            caption: photo.caption,
            alt: `${viewer.unit_code} at ${viewer.location_name}`,
          }))}
          title={viewer.unit_code}
          subtitle={`${viewer.location_name} · ${viewer.city}`}
          details={[
            {
              label: "Dimensions",
              value: `${viewer.dimensions.width} x ${viewer.dimensions.height}`,
            },
            { label: "Facing", value: viewer.facing_direction || "Pending" },
            { label: "Availability", value: viewer.availability.label },
          ]}
          allowDownload={viewer.image_download_allowed}
          onClose={() => setViewer(null)}
        />
      ) : null}
      {showProposal ? (
        <div
          className="planner-modal-backdrop"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && setShowProposal(false)
          }
        >
          <section
            className="planner-proposal-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="proposal-title"
          >
            <header>
              <div>
                <p className="site-code">FORMAL REVIEW REQUEST</p>
                <h2 id="proposal-title">Create campaign proposal</h2>
                <p>
                  {selected.length} selected units ·{" "}
                  {startDate || "Start pending"} to {endDate || "End pending"}
                </p>
              </div>
              <button
                className="ghost"
                type="button"
                onClick={() => setShowProposal(false)}
              >
                Close
              </button>
            </header>
            <form className="planner-proposal-form" onSubmit={submit}>
              <label>
                <span>Campaign name</span>
                <input name="campaign_name" required />
              </label>
              <label>
                <span>Brand / company</span>
                <input name="brand_company" />
              </label>
              <label className="field-full">
                <span>Objective</span>
                <textarea name="objective" rows={2} />
              </label>
              <label>
                <span>Contact name</span>
                <input name="contact_name" required />
              </label>
              <label>
                <span>Email</span>
                <input name="contact_email" type="email" required />
              </label>
              <label>
                <span>Phone</span>
                <input name="contact_phone" />
              </label>
              <label>
                <span>GSTIN</span>
                <input name="billing_gstin" maxLength={15} />
              </label>
              <label className="field-full">
                <span>Billing details</span>
                <textarea name="billing_details" rows={2} />
              </label>
              <label className="field-full">
                <span>Notes</span>
                <textarea name="notes" rows={3} />
              </label>
              <p className="field-full planner-disclaimer">
                This request does not reserve or book inventory. Availability,
                pricing, taxes, production, printing, and mounting remain
                subject to formal confirmation.
              </p>
              <button
                className="submit field-full"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Submitting..." : "Submit proposal"}
              </button>
            </form>
          </section>
        </div>
      ) : null}
    </main>
  );
}

function formatFacetLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

function getEmptyState({
  isLoading,
  eligibleCount,
  resultCount,
  hasActiveFilters,
  hasDates,
  availability,
}: {
  isLoading: boolean;
  eligibleCount: number;
  resultCount: number;
  hasActiveFilters: boolean;
  hasDates: boolean;
  availability: string;
}) {
  if (isLoading || resultCount > 0) return null;
  if (eligibleCount === 0) {
    return {
      title: "No media units are available in this planner",
      message:
        "Ask the media owner to publish or include advertising units in this planner link.",
      showClear: false,
    };
  }
  if (hasDates && availability === "available") {
    return {
      title: "No units are available for these dates",
      message:
        "Try a different campaign period or view all availability statuses.",
      showClear: true,
    };
  }
  if (hasActiveFilters) {
    return {
      title: "No media units match these filters",
      message: "Clear or adjust the filters to see more options.",
      showClear: true,
    };
  }
  return null;
}
