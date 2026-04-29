"use client";

import { useState } from "react";

import { ImageLightbox } from "@/components/image-lightbox";
import { SafeImage } from "@/components/safe-image";

type ImageReferenceCardProps = {
  title: string;
  subtitle: string;
  imageUrl: string | null;
  badge?: string;
  emptyCopy: string;
};

export function ImageReferenceCard({
  title,
  subtitle,
  imageUrl,
  badge,
  emptyCopy,
}: ImageReferenceCardProps) {
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  return (
    <>
      <article className="image-reference-card">
        <div className="image-reference-frame">
          <SafeImage
            src={imageUrl}
            alt={title}
            className="image-reference-asset"
            fallback={
              <div className="image-reference-empty">
                <span>No image available</span>
              </div>
            }
          />
        </div>
        <div className="image-reference-copy">
          <div className="asset-head">
            <div>
              <p className="site-code">{badge ?? "Reference"}</p>
              <h3>{title}</h3>
            </div>
          </div>
          <p className="site-copy">{subtitle}</p>
          <p className="site-copy">{imageUrl ? "Tap to inspect the current live image." : emptyCopy}</p>
          <button
            className="ghost image-reference-action"
            type="button"
            disabled={!imageUrl}
            onClick={() => setIsLightboxOpen(true)}
          >
            {imageUrl ? "Expand preview" : "Awaiting image"}
          </button>
        </div>
      </article>
      {isLightboxOpen ? (
        <ImageLightbox imageUrl={imageUrl} title={title} subtitle={subtitle} onClose={() => setIsLightboxOpen(false)} />
      ) : null}
    </>
  );
}
