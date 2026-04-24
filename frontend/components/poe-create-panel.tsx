"use client";

import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";

import { ImageLightbox } from "@/components/image-lightbox";
import { ImageReferenceCard } from "@/components/image-reference-card";
import type { ApiFieldErrors } from "@/lib/auth";
import type { Booking } from "@/lib/bookings";
import type { Campaign } from "@/lib/campaigns";
import type { InventorySite, InventoryUnit } from "@/lib/inventory";

export type PoeFormState = {
  booking: number;
  executed_on: string;
  verification_status: string;
  notes: string;
  media_type: string;
  captured_at: string;
};

type PoeCreatePanelProps = {
  bookings: Booking[];
  campaigns: Campaign[];
  units: InventoryUnit[];
  sites: InventorySite[];
  form: PoeFormState;
  evidenceFiles: File[];
  fieldErrors: ApiFieldErrors;
  formError: string;
  formSuccess: string;
  isLoading: boolean;
  isSubmitting: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onChange: <K extends keyof PoeFormState>(field: K, value: PoeFormState[K]) => void;
  onFilesChange: (files: File[]) => void;
};

function renderFieldError(fieldErrors: ApiFieldErrors, field: string) {
  const messages = fieldErrors[field];
  if (!messages || messages.length === 0) {
    return null;
  }

  return <p className="field-help field-help-error">{messages.join(" ")}</p>;
}

export function PoeCreatePanel({
  bookings,
  campaigns,
  units,
  sites,
  form,
  evidenceFiles,
  fieldErrors,
  formError,
  formSuccess,
  isLoading,
  isSubmitting,
  onSubmit,
  onChange,
  onFilesChange,
}: PoeCreatePanelProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const selectedBooking = useMemo(() => bookings.find((item) => item.id === form.booking) ?? null, [bookings, form.booking]);
  const selectedCampaign = useMemo(
    () => campaigns.find((item) => item.id === selectedBooking?.campaign) ?? null,
    [campaigns, selectedBooking],
  );
  const selectedUnit = useMemo(
    () => units.find((item) => item.id === selectedBooking?.media_unit) ?? null,
    [selectedBooking, units],
  );
  const selectedSite = useMemo(
    () => sites.find((item) => item.id === selectedUnit?.site) ?? null,
    [selectedUnit, sites],
  );
  const previewEntries = useMemo(
    () =>
      evidenceFiles.map((file) => ({
        name: file.name,
        url: URL.createObjectURL(file),
      })),
    [evidenceFiles],
  );
  const canSubmit = form.booking && form.executed_on && evidenceFiles.length > 0 && !isLoading && !isSubmitting;

  useEffect(() => {
    return () => {
      for (const entry of previewEntries) {
        URL.revokeObjectURL(entry.url);
      }
    };
  }, [previewEntries]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onFilesChange(Array.from(event.target.files ?? []));
  }

  return (
    <>
      <section className="module-card creation-panel">
        <div className="module-head">
          <h2>Create POE record</h2>
          <span>Write access</span>
        </div>
        <p className="section-copy creation-copy">
          Create a proof-of-execution record against a booking and attach real uploaded evidence that is stored in the backend media system.
        </p>
        {formError ? <p className="error">{formError}</p> : null}
        {formSuccess ? <p className="success">{formSuccess}</p> : null}
        <form className="poe-form-grid" onSubmit={onSubmit}>
          <div className="field field-full">
            <label htmlFor="poe-booking">Booking</label>
            <select
              id="poe-booking"
              value={form.booking || ""}
              onChange={(event) => onChange("booking", Number(event.target.value))}
              required
            >
              <option value="" disabled>
                Select booking
              </option>
              {bookings.map((booking) => {
                const campaign = campaigns.find((item) => item.id === booking.campaign);
                const unit = units.find((item) => item.id === booking.media_unit);
                const site = unit ? sites.find((item) => item.id === unit.site) : null;
                return (
                  <option key={booking.id} value={booking.id}>
                    {(campaign?.name ?? `Campaign #${booking.campaign}`) +
                      " · " +
                      (site?.name ?? "Unknown site") +
                      " · " +
                      (unit?.unit_code ?? `Unit #${booking.media_unit}`)}
                  </option>
                );
              })}
            </select>
            {renderFieldError(fieldErrors, "booking")}
          </div>

          <div className="field">
            <label htmlFor="poe-executed-on">Executed on</label>
            <input
              id="poe-executed-on"
              type="date"
              value={form.executed_on}
              onChange={(event) => onChange("executed_on", event.target.value)}
              required
            />
            {renderFieldError(fieldErrors, "executed_on")}
          </div>

          <div className="field">
            <label htmlFor="poe-status">Verification status</label>
            <select
              id="poe-status"
              value={form.verification_status}
              onChange={(event) => onChange("verification_status", event.target.value)}
            >
              <option value="pending">Pending</option>
              <option value="verified">Verified</option>
              <option value="rejected">Rejected</option>
            </select>
            {renderFieldError(fieldErrors, "verification_status")}
          </div>

          <div className="field field-full field-reference-grid">
            <ImageReferenceCard
              title={selectedSite?.name ?? "Site reference"}
              subtitle={selectedSite ? `${selectedSite.city}, ${selectedSite.state}` : "Choose a booking to load the site image"}
              imageUrl={selectedSite?.primary_image?.image_url ?? null}
              badge="Site"
              emptyCopy="No site image has been uploaded yet."
            />
            <ImageReferenceCard
              title={selectedUnit?.unit_code ?? "Media unit reference"}
              subtitle={
                selectedUnit
                  ? `${selectedUnit.width} x ${selectedUnit.height} • ${selectedUnit.status}`
                  : "Choose a booking to load the media unit image"
              }
              imageUrl={selectedUnit?.primary_image?.image_url ?? null}
              badge="Media unit"
              emptyCopy="No media unit image has been uploaded yet."
            />
          </div>

          <div className="field field-full">
            <label htmlFor="poe-notes">Notes</label>
            <textarea
              id="poe-notes"
              value={form.notes}
              onChange={(event) => onChange("notes", event.target.value)}
              placeholder="Field notes about what was executed and any verification context."
              rows={4}
            />
            {renderFieldError(fieldErrors, "notes")}
          </div>

          <div className="field">
            <label htmlFor="poe-media-type">Media type</label>
            <select
              id="poe-media-type"
              value={form.media_type}
              onChange={(event) => onChange("media_type", event.target.value)}
            >
              <option value="image">Image</option>
              <option value="video">Video</option>
              <option value="document">Document</option>
            </select>
            {renderFieldError(fieldErrors, "media_type")}
          </div>

          <div className="field">
            <label htmlFor="poe-captured-at">Captured at</label>
            <input
              id="poe-captured-at"
              type="datetime-local"
              value={form.captured_at}
              onChange={(event) => onChange("captured_at", event.target.value)}
            />
            <p className="field-help">Defaults to the current device time and is stored on each uploaded evidence item.</p>
            {renderFieldError(fieldErrors, "captured_at")}
          </div>

          <div className="field field-full">
            <label htmlFor="poe-evidence-files">Proof images</label>
            <input
              id="poe-evidence-files"
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              onChange={handleFileChange}
              required
            />
            <p className="field-help">Choose one or more installation photos to attach to this proof-of-execution record.</p>
            {renderFieldError(fieldErrors, "image")}
            {renderFieldError(fieldErrors, "non_field_errors")}
          </div>

          {selectedBooking ? (
            <div className="field-full field-capture-summary">
              <article className="module-stat field-summary-card">
                <p className="stat-label">Campaign</p>
                <p className="stat-value field-summary-value">{selectedCampaign?.name ?? "Unknown campaign"}</p>
                <p className="site-copy">{selectedCampaign?.code ?? "No campaign code"}</p>
              </article>
              <article className="module-stat field-summary-card">
                <p className="stat-label">Scheduled window</p>
                <p className="stat-value field-summary-value">
                  {selectedBooking.start_date} to {selectedBooking.end_date}
                </p>
                <p className="site-copy">{selectedUnit?.unit_code ?? "Unknown unit"}</p>
              </article>
            </div>
          ) : null}

          {previewEntries.length > 0 ? (
            <div className="field-full">
              <div className="module-head">
                <h2>Selected evidence</h2>
                <span>{previewEntries.length} item(s)</span>
              </div>
              <div className="capture-preview-grid">
                {previewEntries.map((entry) => (
                  <article className="capture-preview-card" key={entry.url}>
                    <button className="capture-preview-button" type="button" onClick={() => setPreviewUrl(entry.url)}>
                      <img className="capture-preview-image" src={entry.url} alt={entry.name} />
                    </button>
                    <p className="site-copy capture-preview-name">{entry.name}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          <div className="form-actions field-full">
            <button className="submit" type="submit" disabled={!canSubmit}>
              {isSubmitting ? "Creating POE..." : "Create POE"}
            </button>
          </div>
        </form>
      </section>

      {previewUrl ? (
        <ImageLightbox imageUrl={previewUrl} title="Evidence preview" subtitle="Selected before upload" onClose={() => setPreviewUrl(null)} />
      ) : null}
    </>
  );
}
