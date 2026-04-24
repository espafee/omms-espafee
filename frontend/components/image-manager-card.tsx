"use client";

import type { ReactNode } from "react";
import { type FormEvent, useState } from "react";

import { ImageLightbox } from "@/components/image-lightbox";
import type { InventoryImage } from "@/lib/inventory";

type ImageManagerCardProps = {
  formIdPrefix: string;
  title: string;
  eyebrow: string;
  description: string;
  meta: string;
  images?: InventoryImage[] | null;
  primaryImage?: InventoryImage | null;
  canManage: boolean;
  uploadLabel: string;
  emptyCopy: string;
  onUpload: (payload: { file: File; caption: string; isPrimary: boolean }) => Promise<void>;
  onMarkPrimary: (imageId: number) => Promise<void>;
  onDelete: (imageId: number) => Promise<void>;
  headerAction?: ReactNode;
  badges?: Array<{ label: string; tone?: string }>;
};

export function ImageManagerCard({
  formIdPrefix,
  title,
  eyebrow,
  description,
  meta,
  images,
  primaryImage,
  canManage,
  uploadLabel,
  emptyCopy,
  onUpload,
  onMarkPrimary,
  onDelete,
  headerAction,
  badges = [],
}: ImageManagerCardProps) {
  const safeImages = images ?? [];
  const safePrimaryImage = primaryImage ?? null;
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [isPrimary, setIsPrimary] = useState(!safePrimaryImage);
  const [formError, setFormError] = useState("");
  const [formSuccess, setFormSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeImageId, setActiveImageId] = useState<number | null>(null);
  const [lightboxImage, setLightboxImage] = useState<InventoryImage | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || isSubmitting) {
      return;
    }

    setFormError("");
    setFormSuccess("");
    setIsSubmitting(true);

    try {
      await onUpload({
        file: selectedFile,
        caption,
        isPrimary,
      });
      setSelectedFile(null);
      setCaption("");
      setIsPrimary(false);
      setFormSuccess("Image uploaded successfully.");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to upload the image.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePrimarySelect(imageId: number) {
    if (activeImageId) {
      return;
    }

    setFormError("");
    setFormSuccess("");
    setActiveImageId(imageId);

    try {
      await onMarkPrimary(imageId);
      setFormSuccess("Primary image updated.");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to update the primary image.");
    } finally {
      setActiveImageId(null);
    }
  }

  async function handleDelete(imageId: number) {
    if (activeImageId) {
      return;
    }

    setFormError("");
    setFormSuccess("");
    setActiveImageId(imageId);

    try {
      await onDelete(imageId);
      setFormSuccess("Image removed successfully.");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to remove the image.");
    } finally {
      setActiveImageId(null);
    }
  }

  return (
    <>
      <article className="module-card image-manager-card">
        <div className="module-head">
          <div>
            <p className="site-code">{eyebrow}</p>
            <h2>{title}</h2>
          </div>
          <div className="card-head-actions">
            <span>{safeImages.length} image(s)</span>
            {headerAction}
          </div>
        </div>
        <p className="site-copy">{description}</p>
        <p className="site-copy image-manager-meta">{meta}</p>
        {badges.length > 0 ? (
          <div className="unit-meta-chip-row" aria-label={`${title} metadata`}>
            {badges.map((badge) => (
              <span className={`unit-meta-chip ${badge.tone ? `status-${badge.tone}` : ""}`} key={`${title}-${badge.label}`}>
                {badge.label}
              </span>
            ))}
          </div>
        ) : null}

        <button
          className="image-manager-hero"
          type="button"
          disabled={!safePrimaryImage?.image_url}
          onClick={() => setLightboxImage(safePrimaryImage)}
        >
          {safePrimaryImage?.image_url ? (
            <img
              className="image-manager-hero-image"
              src={safePrimaryImage.image_url}
              alt={safePrimaryImage.caption || title}
            />
          ) : (
            <div className="image-manager-empty">
              <span>{emptyCopy}</span>
            </div>
          )}
        </button>

        <div className="image-thumb-grid">
          {safeImages.map((image) => (
            <article className="image-thumb-card" key={image.id}>
              <button className="image-thumb-button" type="button" onClick={() => setLightboxImage(image)}>
                {image.image_url ? (
                  <img className="image-thumb" src={image.image_url} alt={image.caption || title} />
                ) : (
                  <div className="image-reference-empty asset-image-placeholder">
                    <span>Preview unavailable</span>
                  </div>
                )}
              </button>
              <div className="image-thumb-copy">
                <p className="site-copy">{image.caption || "Untitled image"}</p>
                <div className="image-thumb-badges">
                  {image.is_primary ? <span className="status-pill status-approved">Primary</span> : null}
                  <span className="site-code">{new Date(image.uploaded_at).toLocaleDateString("en-IN")}</span>
                </div>
                {canManage ? (
                  <div className="image-thumb-actions">
                    {!image.is_primary ? (
                      <button
                        className="ghost"
                        type="button"
                        disabled={activeImageId === image.id}
                        onClick={() => void handlePrimarySelect(image.id)}
                      >
                        {activeImageId === image.id ? "Saving..." : "Make primary"}
                      </button>
                    ) : null}
                    <button
                      className="ghost ghost-danger"
                      type="button"
                      disabled={activeImageId === image.id}
                      onClick={() => void handleDelete(image.id)}
                    >
                      {activeImageId === image.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        {safeImages.length === 0 ? <p className="empty-state">{emptyCopy}</p> : null}
        {formError ? <p className="error">{formError}</p> : null}
        {formSuccess ? <p className="success">{formSuccess}</p> : null}

        {canManage ? (
          <form className="image-upload-form" onSubmit={handleSubmit}>
            <div className="field field-full">
              <label htmlFor={`${formIdPrefix}-file`}>{uploadLabel}</label>
              <input
                id={`${formIdPrefix}-file`}
                type="file"
                accept="image/*"
                onChange={(event) => {
                  setFormError("");
                  setFormSuccess("");
                  setSelectedFile(event.target.files?.[0] ?? null);
                }}
                required
              />
              <p className="field-help">
                {selectedFile
                  ? `${selectedFile.name} selected (${Math.max(1, Math.round(selectedFile.size / 1024))} KB).`
                  : "Upload a JPG, PNG, or WebP image. The browser will send it as multipart form data."}
              </p>
            </div>
            <div className="field">
              <label htmlFor={`${formIdPrefix}-caption`}>Caption</label>
              <input
                id={`${formIdPrefix}-caption`}
                value={caption}
                onChange={(event) => setCaption(event.target.value)}
                placeholder="Front-facing view, night illumination, installation close-up..."
              />
            </div>
            <label className="checkbox-field" htmlFor={`${formIdPrefix}-primary`}>
              <input
                id={`${formIdPrefix}-primary`}
                type="checkbox"
                checked={isPrimary}
                onChange={(event) => setIsPrimary(event.target.checked)}
              />
              <span>Set as primary image</span>
            </label>
            <div className="form-actions field-full">
              <button className="submit" type="submit" disabled={!selectedFile || isSubmitting}>
                {isSubmitting ? "Uploading..." : "Upload image"}
              </button>
            </div>
          </form>
        ) : null}
      </article>

      {lightboxImage ? (
        <ImageLightbox
          imageUrl={lightboxImage.image_url}
          title={title}
          subtitle={lightboxImage.caption || meta}
          onClose={() => setLightboxImage(null)}
        />
      ) : null}
    </>
  );
}
