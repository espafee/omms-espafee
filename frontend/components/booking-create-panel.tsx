"use client";

import type { FormEvent } from "react";

import { ImageReferenceCard } from "@/components/image-reference-card";
import type { ApiFieldErrors } from "@/lib/auth";
import type { BookingCreateInput } from "@/lib/bookings";
import type { Campaign } from "@/lib/campaigns";
import { formatMediaUnitSiteType, type InventorySite, type InventoryUnit } from "@/lib/inventory";

export type BookingFormState = BookingCreateInput & {
  site: number;
};

type BookingCreatePanelProps = {
  campaigns: Campaign[];
  sites: InventorySite[];
  units: InventoryUnit[];
  selectedSite: InventorySite | null;
  selectedUnit: InventoryUnit | null;
  form: BookingFormState;
  fieldErrors: ApiFieldErrors;
  formError: string;
  formSuccess: string;
  isLoading: boolean;
  isSubmitting: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onChange: <K extends keyof BookingFormState>(field: K, value: BookingFormState[K]) => void;
};

function renderFieldError(fieldErrors: ApiFieldErrors, field: string) {
  const messages = fieldErrors[field];
  if (!messages || messages.length === 0) {
    return null;
  }

  return <p className="field-help field-help-error">{messages.join(" ")}</p>;
}

export function BookingCreatePanel({
  campaigns,
  sites,
  units,
  selectedSite,
  selectedUnit,
  form,
  fieldErrors,
  formError,
  formSuccess,
  isLoading,
  isSubmitting,
  onSubmit,
  onChange,
}: BookingCreatePanelProps) {
  const siteUnits = units.filter((unit) => unit.site === form.site);
  const isSubmitDisabled =
    isLoading ||
    isSubmitting ||
    campaigns.length === 0 ||
    sites.length === 0 ||
    !form.campaign ||
    !form.site ||
    !form.media_unit ||
    !form.start_date ||
    !form.end_date ||
    !form.booked_rate;

  return (
    <section className="module-card creation-panel">
      <div className="module-head">
        <h2>Create booking</h2>
        <span>Write access</span>
      </div>
      <p className="section-copy creation-copy">
        Reserve a specific inventory unit for a campaign. Site and unit previews update live from the actual inventory image library so schedulers can confirm the right location before saving.
      </p>
      {formError ? <p className="error">{formError}</p> : null}
      {formSuccess ? <p className="success">{formSuccess}</p> : null}
      <form className="booking-form-grid" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="booking-campaign">Campaign</label>
          <select
            id="booking-campaign"
            value={form.campaign || ""}
            onChange={(event) => onChange("campaign", Number(event.target.value))}
            required
          >
            <option value="" disabled>
              Select campaign
            </option>
            {campaigns.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>
                {campaign.name} ({campaign.code})
              </option>
            ))}
          </select>
          {renderFieldError(fieldErrors, "campaign")}
        </div>

        <div className="field">
          <label htmlFor="booking-site">Site</label>
          <select
            id="booking-site"
            value={form.site || ""}
            onChange={(event) => onChange("site", Number(event.target.value))}
            required
          >
            <option value="" disabled>
              Select site
            </option>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name} ({site.code})
              </option>
            ))}
          </select>
          {renderFieldError(fieldErrors, "site")}
        </div>

        <div className="field">
          <label htmlFor="booking-unit">Unit</label>
          <select
            id="booking-unit"
            value={form.media_unit || ""}
            onChange={(event) => onChange("media_unit", Number(event.target.value))}
            required
            disabled={!form.site}
          >
            <option value="" disabled>
              {form.site ? "Select unit" : "Select site first"}
            </option>
            {siteUnits.map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.unit_code} · {unit.facing_direction || "Direction pending"} · {formatMediaUnitSiteType(unit.site_type)}
              </option>
            ))}
          </select>
          {renderFieldError(fieldErrors, "media_unit")}
        </div>

        <div className="field">
          <label htmlFor="booking-status">Status</label>
          <select
            id="booking-status"
            value={form.status}
            onChange={(event) => onChange("status", event.target.value)}
          >
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="live">Live</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          {renderFieldError(fieldErrors, "status")}
        </div>

        <div className="field field-full booking-preview-strip">
          <ImageReferenceCard
            title={selectedSite?.name ?? "Site preview"}
            subtitle={selectedSite ? `${selectedSite.city}, ${selectedSite.state}` : "Choose a site to see its primary image"}
            imageUrl={selectedSite?.primary_image?.image_url ?? null}
            badge="Site"
            emptyCopy="No primary site image has been uploaded yet."
          />
          <ImageReferenceCard
            title={selectedUnit?.unit_code ?? "Media unit preview"}
            subtitle={
              selectedUnit
                ? `${selectedUnit.width} x ${selectedUnit.height} • ${selectedUnit.facing_direction || "Direction pending"} • ${formatMediaUnitSiteType(selectedUnit.site_type)}`
                : "Choose a media unit to see its primary image"
            }
            imageUrl={selectedUnit?.primary_image?.image_url ?? null}
            badge="Media unit"
            emptyCopy="No primary media unit image has been uploaded yet."
          />
        </div>

        <div className="field">
          <label htmlFor="booking-start-date">Start date</label>
          <input
            id="booking-start-date"
            type="date"
            value={form.start_date}
            onChange={(event) => onChange("start_date", event.target.value)}
            required
          />
          {renderFieldError(fieldErrors, "start_date")}
        </div>

        <div className="field">
          <label htmlFor="booking-end-date">End date</label>
          <input
            id="booking-end-date"
            type="date"
            value={form.end_date}
            onChange={(event) => onChange("end_date", event.target.value)}
            required
          />
          {renderFieldError(fieldErrors, "end_date")}
        </div>

        <div className="field field-rate">
          <label htmlFor="booking-rate">Booked rate</label>
          <input
            id="booking-rate"
            type="number"
            min="0"
            step="0.01"
            value={form.booked_rate}
            onChange={(event) => onChange("booked_rate", event.target.value)}
            placeholder="70000"
            required
          />
          <p className="field-help">Defaults from the selected unit’s monthly rate and can be adjusted before save.</p>
          {renderFieldError(fieldErrors, "booked_rate")}
        </div>

        <div className="field field-full">
          <label htmlFor="booking-remarks">Remarks</label>
          <textarea
            id="booking-remarks"
            value={form.remarks}
            onChange={(event) => onChange("remarks", event.target.value)}
            placeholder="Any scheduling or operations notes for this booking."
            rows={4}
          />
          {renderFieldError(fieldErrors, "remarks")}
          {renderFieldError(fieldErrors, "non_field_errors")}
        </div>

        <div className="form-actions field-full">
          <button className="submit" type="submit" disabled={isSubmitDisabled}>
            {isSubmitting ? "Creating booking..." : "Create booking"}
          </button>
        </div>
      </form>
    </section>
  );
}
