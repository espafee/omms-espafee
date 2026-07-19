"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";

import { ImageLightbox } from "@/components/image-lightbox";
import {
  fetchCompletePublicPlanner,
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
const DATE_REQUIRED_MESSAGE = "Select campaign start and end dates before requesting a formal estimate.";
const DATE_RANGE_MESSAGE = "Campaign end date must be on or after the start date.";
const UNIT_REQUIRED_MESSAGE = "Select at least one advertising unit.";

type ProposalFieldErrors = Partial<Record<
  "campaign_name" | "brand_company" | "contact_name" | "contact_email" | "dates" | "units",
  string
>>;

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
  const [dateError, setDateError] = useState("");
  const [proposalErrors, setProposalErrors] = useState<ProposalFieldErrors>({});
  const [submissionError, setSubmissionError] = useState("");
  const startDateRef = useRef<HTMLInputElement | null>(null);
  const endDateRef = useRef<HTMLInputElement | null>(null);

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
        await fetchCompletePublicPlanner(token, {
          ...filters,
          start_date: startDate,
          end_date: endDate,
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
    emptyReason: payload?.meta?.empty_reason ?? null,
    hasActiveFilters,
    hasDates: Boolean(startDate && endDate),
    availability: filters.availability,
  });
  const hasValidCampaignDates = Boolean(startDate && endDate && startDate <= endDate);
  const displayedUnitCount = payload?.count ?? payload?.results.length ?? 0;
  const displayedLocationCount =
    payload?.meta?.unique_location_count ??
    countUniqueLocations(payload?.results ?? []);

  function focusDateField(field: "start" | "end") {
    const target = field === "start" ? startDateRef.current : endDateRef.current;
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    target?.focus({ preventScroll: true });
  }

  function validateCampaignDates({ focus = false } = {}) {
    if (!startDate || !endDate) {
      setDateError(DATE_REQUIRED_MESSAGE);
      if (focus) focusDateField(!startDate ? "start" : "end");
      return false;
    }
    if (startDate > endDate) {
      setDateError(DATE_RANGE_MESSAGE);
      if (focus) focusDateField("end");
      return false;
    }
    setDateError("");
    return true;
  }

  function openProposalRequest() {
    if (!selected.length) {
      setDateError(UNIT_REQUIRED_MESSAGE);
      return;
    }
    if (!validateCampaignDates({ focus: true })) {
      return;
    }
    setProposalErrors({});
    setSubmissionError("");
    setReference("");
    setShowProposal(true);
  }

  function closeProposalAndFocusDates() {
    setShowProposal(false);
    window.setTimeout(() => focusDateField(!startDate ? "start" : "end"), 0);
  }

  function clearProposalError(field: keyof ProposalFieldErrors) {
    setProposalErrors((current) => {
      if (!current[field]) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    const nextErrors: ProposalFieldErrors = {};
    if (!validateCampaignDates()) {
      nextErrors.dates = !startDate || !endDate ? DATE_REQUIRED_MESSAGE : DATE_RANGE_MESSAGE;
    }
    if (!selected.length) {
      nextErrors.units = UNIT_REQUIRED_MESSAGE;
    }
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const campaignName = String(form.get("campaign_name") || "").trim();
    const brandCompany = String(form.get("brand_company") || "").trim();
    const contactName = String(form.get("contact_name") || "").trim();
    const contactEmail = String(form.get("contact_email") || "").trim();
    const emailInput = formElement.elements.namedItem("contact_email") as HTMLInputElement | null;
    if (!campaignName) nextErrors.campaign_name = "Enter a campaign name.";
    if (!brandCompany) nextErrors.brand_company = "Enter the brand or company name.";
    if (!contactName) nextErrors.contact_name = "Enter a contact name.";
    if (!contactEmail) {
      nextErrors.contact_email = "Enter a contact email.";
    } else if (emailInput && !emailInput.validity.valid) {
      nextErrors.contact_email = "Enter a valid email address.";
    }
    if (Object.keys(nextErrors).length) {
      setProposalErrors(nextErrors);
      const firstErrorField = Object.keys(nextErrors)[0];
      if (firstErrorField === "dates") {
        focusDateField(!startDate ? "start" : "end");
      } else {
        const input = formElement.elements.namedItem(firstErrorField) as HTMLElement | null;
        input?.focus();
      }
      return;
    }
    setIsSubmitting(true);
    setSubmissionError("");
    setProposalErrors({});
    try {
      const result = await submitPublicProposal(token, {
        campaign_name: campaignName,
        brand_company: brandCompany,
        objective: form.get("objective"),
        requested_start_date: startDate,
        requested_end_date: endDate,
        contact_name: contactName,
        contact_email: contactEmail,
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
      setSubmissionError(
        submitError instanceof Error
          ? submitError.message
          : "We could not submit the proposal. Please check your connection and try again.",
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
            ref={startDateRef}
            id="planner-start-date"
            type="date"
            value={startDate}
            aria-invalid={Boolean(dateError && !startDate)}
            aria-describedby={dateError ? "planner-date-error" : undefined}
            className={dateError && !startDate ? "field-error-input" : ""}
            onChange={(event) => {
              setStartDate(event.target.value);
              setDateError("");
            }}
          />
        </label>
        <label>
          <span>End date</span>
          <input
            ref={endDateRef}
            id="planner-end-date"
            type="date"
            min={startDate}
            value={endDate}
            aria-invalid={Boolean(dateError && (!endDate || startDate > endDate))}
            aria-describedby={dateError ? "planner-date-error" : undefined}
            className={dateError && (!endDate || startDate > endDate) ? "field-error-input" : ""}
            onChange={(event) => {
              setEndDate(event.target.value);
              setDateError("");
            }}
          />
        </label>
        <span className="planner-live-indicator">Live availability</span>
        <p id="planner-date-error" className="planner-date-validation" aria-live="polite">
          {dateError || (selected.length ? "Select dates before requesting a formal estimate." : "")}
        </p>
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
              : `${displayedUnitCount} advertising unit${displayedUnitCount === 1 ? "" : "s"} across ${displayedLocationCount} location${displayedLocationCount === 1 ? "" : "s"}`}
          </h2>
          {!isLoading && payload?.meta?.eligible_unit_count !== undefined ? (
            <span className="planner-count-note">
              {payload.meta.eligible_unit_count} eligible advertising unit{payload.meta.eligible_unit_count === 1 ? "" : "s"}
              {" · "}
              {payload.meta.eligible_location_count ?? displayedLocationCount} eligible location{(payload.meta.eligible_location_count ?? displayedLocationCount) === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
        <p>Advertising units and physical locations are counted separately.</p>
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
            <article className="planner-unit-card" key={unit.public_id} data-unit-id={unit.public_id}>
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
          aria-describedby="planner-basket-help"
          onClick={openProposalRequest}
        >
          Request formal estimate
        </button>
        <span id="planner-basket-help" className="planner-basket-help" aria-live="polite">
          {!selected.length ? UNIT_REQUIRED_MESSAGE : dateError || "Dates are required before formal review."}
        </span>
      </aside>
      {reference ? (
        <div className="planner-success" role="status">
          <strong>Proposal submitted successfully</strong>
          <span>
            Reference {reference}. The media owner will review availability and
            prepare a formal estimate.
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
                <div className="planner-proposal-summary">
                  <span>
                    {selected.length} selected unit{selected.length === 1 ? "" : "s"}
                  </span>
                  {hasValidCampaignDates ? (
                    <span>
                      Campaign dates: {formatPlannerDate(startDate)} - {formatPlannerDate(endDate)}
                    </span>
                  ) : (
                    <span>Campaign dates have not been selected.</span>
                  )}
                </div>
              </div>
              <button
                className="ghost"
                type="button"
                onClick={() => setShowProposal(false)}
              >
                Close
              </button>
            </header>
            <form className="planner-proposal-form" onSubmit={submit} noValidate>
              <label>
                <span>Campaign name</span>
                <input
                  name="campaign_name"
                  aria-invalid={Boolean(proposalErrors.campaign_name)}
                  aria-describedby={proposalErrors.campaign_name ? "campaign-name-error" : undefined}
                  onChange={() => clearProposalError("campaign_name")}
                />
                {proposalErrors.campaign_name ? (
                  <small id="campaign-name-error" className="field-error-text">
                    {proposalErrors.campaign_name}
                  </small>
                ) : null}
              </label>
              <label>
                <span>Brand / company</span>
                <input
                  name="brand_company"
                  aria-invalid={Boolean(proposalErrors.brand_company)}
                  aria-describedby={proposalErrors.brand_company ? "brand-company-error" : undefined}
                  onChange={() => clearProposalError("brand_company")}
                />
                {proposalErrors.brand_company ? (
                  <small id="brand-company-error" className="field-error-text">
                    {proposalErrors.brand_company}
                  </small>
                ) : null}
              </label>
              <label className="field-full">
                <span>Objective</span>
                <textarea name="objective" rows={2} />
              </label>
              <label>
                <span>Contact name</span>
                <input
                  name="contact_name"
                  aria-invalid={Boolean(proposalErrors.contact_name)}
                  aria-describedby={proposalErrors.contact_name ? "contact-name-error" : undefined}
                  onChange={() => clearProposalError("contact_name")}
                />
                {proposalErrors.contact_name ? (
                  <small id="contact-name-error" className="field-error-text">
                    {proposalErrors.contact_name}
                  </small>
                ) : null}
              </label>
              <label>
                <span>Email</span>
                <input
                  name="contact_email"
                  type="email"
                  aria-invalid={Boolean(proposalErrors.contact_email)}
                  aria-describedby={proposalErrors.contact_email ? "contact-email-error" : undefined}
                  onChange={() => clearProposalError("contact_email")}
                />
                {proposalErrors.contact_email ? (
                  <small id="contact-email-error" className="field-error-text">
                    {proposalErrors.contact_email}
                  </small>
                ) : null}
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
              {proposalErrors.dates || proposalErrors.units ? (
                <p className="field-full planner-inline-error" role="alert">
                  {proposalErrors.dates || proposalErrors.units}
                </p>
              ) : null}
              {submissionError ? (
                <p className="field-full planner-inline-error" role="alert">
                  {submissionError}
                </p>
              ) : null}
              {!hasValidCampaignDates ? (
                <button className="ghost field-full" type="button" onClick={closeProposalAndFocusDates}>
                  Return to planner
                </button>
              ) : null}
              <button
                className="submit field-full"
                type="submit"
                disabled={isSubmitting || !hasValidCampaignDates}
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

function formatPlannerDate(value: string) {
  if (!value) return "";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function countUniqueLocations(units: PublicPlannerUnit[]) {
  return new Set(units.map((unit) => unit.location_name.trim().toLowerCase()).filter(Boolean)).size;
}

function getEmptyState({
  isLoading,
  eligibleCount,
  resultCount,
  emptyReason,
  hasActiveFilters,
  hasDates,
  availability,
}: {
  isLoading: boolean;
  eligibleCount: number;
  resultCount: number;
  emptyReason: "no_eligible_inventory" | "no_date_availability" | "no_filter_matches" | null;
  hasActiveFilters: boolean;
  hasDates: boolean;
  availability: string;
}) {
  if (isLoading || resultCount > 0) return null;
  if (emptyReason === "no_eligible_inventory" || eligibleCount === 0) {
    return {
      title: "No media units are available in this planner",
      message:
        "Ask the media owner to publish or include advertising units in this planner link.",
      showClear: false,
    };
  }
  if (emptyReason === "no_date_availability" || (hasDates && availability === "available")) {
    return {
      title: "No units are available for these dates",
      message:
        "Try a different campaign period or view all availability statuses.",
      showClear: true,
    };
  }
  if (emptyReason === "no_filter_matches" || hasActiveFilters) {
    return {
      title: "No media units match these filters",
      message: "Clear or adjust the filters to see more options.",
      showClear: true,
    };
  }
  return null;
}
