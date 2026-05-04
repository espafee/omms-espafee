"use client";

import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";

import { ImageLightbox } from "@/components/image-lightbox";
import { ImageReferenceCard } from "@/components/image-reference-card";
import type { ApiFieldErrors } from "@/lib/auth";
import type { Booking } from "@/lib/bookings";
import type { Campaign } from "@/lib/campaigns";
import type { InventorySite, InventoryUnit } from "@/lib/inventory";

export type PoeCaptureFormState = {
  booking: number;
  executed_on: string;
  notes: string;
  media_type: string;
};

type PoeFieldCaptureFormProps = {
  bookings: Booking[];
  campaigns: Campaign[];
  units: InventoryUnit[];
  sites: InventorySite[];
  form: PoeCaptureFormState;
  evidenceFiles: File[];
  fieldErrors: ApiFieldErrors;
  formError: string;
  formSuccess: string;
  isLoading: boolean;
  isSubmitting: boolean;
  submitLabel: string;
  headerTitle: string;
  headerCopy: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onChange: <K extends keyof PoeCaptureFormState>(field: K, value: PoeCaptureFormState[K]) => void;
  onFilesChange: (files: File[]) => void;
};

function renderFieldError(fieldErrors: ApiFieldErrors, field: string) {
  const messages = fieldErrors[field];
  if (!messages || messages.length === 0) {
    return null;
  }

  return <p className="field-help field-help-error">{messages.join(" ")}</p>;
}

export function PoeFieldCaptureForm({
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
  submitLabel,
  headerTitle,
  headerCopy,
  onSubmit,
  onChange,
  onFilesChange,
}: PoeFieldCaptureFormProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const bookingDetails = useMemo(() => {
    const booking = bookings.find((item) => item.id === form.booking) ?? null;
    const campaign = booking ? campaigns.find((item) => item.id === booking.campaign) ?? null : null;
    const unit = booking ? units.find((item) => item.id === booking.media_unit) ?? null : null;
    const site = unit ? sites.find((item) => item.id === unit.site) ?? null : null;

    return { booking, campaign, unit, site };
  }, [bookings, campaigns, form.booking, sites, units]);

  const previewEntries = useMemo(
    () =>
      evidenceFiles.map((file) => ({
        name: file.name,
        url: URL.createObjectURL(file),
      })),
    [evidenceFiles],
  );

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
      <section className="module-card creation-panel field-capture-panel">
        <div className="module-head">
          <div>
            <p className="site-code">Field execution</p>
            <h2>{headerTitle}</h2>
          </div>
          <span>Operations</span>
        </div>
        <p className="section-copy creation-copy">{headerCopy}</p>
        {formError ? <p className="error">{formError}</p> : null}
        {formSuccess ? <p className="success">{formSuccess}</p> : null}

        <form className="poe-capture-grid" onSubmit={onSubmit}>
          <div className="field field-full">
            <label htmlFor="poe-capture-booking">Booking</label>
            <select
              id="poe-capture-booking"
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
            <label htmlFor="poe-capture-date">Executed on</label>
            <input
              id="poe-capture-date"
              type="date"
              value={form.executed_on}
              onChange={(event) => onChange("executed_on", event.target.value)}
              required
            />
            {renderFieldError(fieldErrors, "executed_on")}
          </div>

          <div className="field">
            <label htmlFor="poe-capture-media-type">Media type</label>
            <select
              id="poe-capture-media-type"
              value={form.media_type}
              onChange={(event) => onChange("media_type", event.target.value)}
            >
              <option value="image">Image</option>
              <option value="video">Video</option>
              <option value="document">Document</option>
            </select>
            <p className="field-help">Each uploaded evidence item is attached to this POE record for review.</p>
            {renderFieldError(fieldErrors, "media_type")}
          </div>

          <div className="field field-full">
            <label htmlFor="poe-capture-files">Evidence images</label>
            <input
              id="poe-capture-files"
              type="file"
              accept="image/*"
              capture="environment"
              multiple
              onChange={handleFileChange}
              required
            />
            <p className="field-help">Select one or more images from the device camera or gallery before submitting.</p>
            {renderFieldError(fieldErrors, "image")}
            {renderFieldError(fieldErrors, "non_field_errors")}
          </div>

          <div className="field field-full">
            <label htmlFor="poe-capture-notes">Notes</label>
            <textarea
              id="poe-capture-notes"
              value={form.notes}
              onChange={(event) => onChange("notes", event.target.value)}
              placeholder="Installed successfully, panel illuminated, facing westbound lane..."
              rows={4}
            />
            {renderFieldError(fieldErrors, "notes")}
          </div>

          {bookingDetails.booking ? (
            <div className="field-full field-capture-summary">
              <article className="module-stat field-summary-card">
                <p className="stat-label">Campaign</p>
                <p className="stat-value field-summary-value">{bookingDetails.campaign?.name ?? "Unknown campaign"}</p>
                <p className="site-copy">{bookingDetails.campaign?.code ?? "No campaign code"}</p>
              </article>
              <article className="module-stat field-summary-card">
                <p className="stat-label">Scheduled window</p>
                <p className="stat-value field-summary-value">
                  {bookingDetails.booking.start_date} to {bookingDetails.booking.end_date}
                </p>
                <p className="site-copy">{bookingDetails.unit?.unit_code ?? "Unknown unit"}</p>
              </article>
            </div>
          ) : null}

          {bookingDetails.booking ? (
            <div className="field-full field-reference-grid">
              <ImageReferenceCard
                title={bookingDetails.site?.name ?? "Site reference"}
                subtitle={bookingDetails.site ? `${bookingDetails.site.city}, ${bookingDetails.site.state}` : "No site selected"}
                imageUrl={bookingDetails.site?.primary_image?.image_url ?? null}
                badge="Site"
                emptyCopy="No site image has been uploaded yet."
              />
              <ImageReferenceCard
                title={bookingDetails.unit?.unit_code ?? "Unit reference"}
                subtitle={
                  bookingDetails.unit
                    ? `${bookingDetails.unit.width} x ${bookingDetails.unit.height} • ${bookingDetails.unit.status}`
                    : "No media unit selected"
                }
                imageUrl={bookingDetails.unit?.primary_image?.image_url ?? null}
                badge="Media unit"
                emptyCopy="No media unit image has been uploaded yet."
              />
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
            <button
              className="submit submit-wide-mobile"
              type="submit"
              disabled={isLoading || isSubmitting || !form.booking || !form.executed_on || evidenceFiles.length === 0}
            >
              {isSubmitting ? "Submitting proof..." : submitLabel}
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
