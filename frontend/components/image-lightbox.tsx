"use client";

import { useEffect, useRef, useState } from "react";

import { SafeImage } from "@/components/safe-image";

export type LightboxImage = { url: string; alt?: string; caption?: string };

type ImageLightboxProps = {
  imageUrl?: string | null;
  images?: LightboxImage[];
  initialIndex?: number;
  title: string;
  subtitle?: string;
  details?: Array<{ label: string; value: string }>;
  allowDownload?: boolean;
  onClose: () => void;
};

export function ImageLightbox({
  imageUrl,
  images,
  initialIndex = 0,
  title,
  subtitle,
  details = [],
  allowDownload = false,
  onClose,
}: ImageLightboxProps) {
  const gallery = images?.length
    ? images
    : imageUrl
      ? [{ url: imageUrl, alt: title, caption: subtitle }]
      : [];
  const [activeIndex, setActiveIndex] = useState(
    Math.min(initialIndex, Math.max(gallery.length - 1, 0)),
  );
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const touchStartRef = useRef<number | null>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowLeft" && gallery.length > 1)
        setActiveIndex(
          (value) => (value - 1 + gallery.length) % gallery.length,
        );
      if (event.key === "ArrowRight" && gallery.length > 1)
        setActiveIndex((value) => (value + 1) % gallery.length);
      if (event.key !== "Tab") return;
      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.classList.remove("modal-open");
      previouslyFocused?.focus();
    };
  }, [gallery.length, onClose]);

  if (!gallery.length) return null;
  const active = gallery[activeIndex];
  const showNavigation = gallery.length > 1;
  const move = (direction: number) =>
    setActiveIndex(
      (value) => (value + direction + gallery.length) % gallery.length,
    );

  return (
    <div
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        className="lightbox-backdrop"
        type="button"
        aria-label="Close photo viewer"
        onClick={onClose}
      />
      <div className="lightbox-panel inventory-lightbox-panel" ref={panelRef}>
        <header className="lightbox-head">
          <div>
            <p className="site-code">PHOTO VIEWER</p>
            <h2>{title}</h2>
            {subtitle ? <p className="site-copy">{subtitle}</p> : null}
          </div>
          <button
            ref={closeRef}
            className="ghost"
            type="button"
            onClick={onClose}
            aria-label="Close photo viewer"
          >
            Close
          </button>
        </header>
        <div
          className="inventory-lightbox-stage"
          onTouchStart={(event) => {
            touchStartRef.current = event.changedTouches[0]?.clientX ?? null;
          }}
          onTouchEnd={(event) => {
            const start = touchStartRef.current;
            const end = event.changedTouches[0]?.clientX;
            if (
              start !== null &&
              end !== undefined &&
              Math.abs(end - start) > 55 &&
              showNavigation
            )
              move(end < start ? 1 : -1);
            touchStartRef.current = null;
          }}
        >
          <span className="lightbox-loading" aria-hidden="true">
            Loading photo...
          </span>
          {showNavigation ? (
            <button
              className="lightbox-nav lightbox-nav-prev"
              type="button"
              onClick={() => move(-1)}
              aria-label="Previous photo"
            >
              Previous
            </button>
          ) : null}
          <SafeImage
            src={active.url}
            alt={active.alt || `${title} photo ${activeIndex + 1}`}
            className="lightbox-image inventory-lightbox-image"
            loading="eager"
            fallback={
              <div className="image-reference-empty lightbox-image lightbox-image-fallback">
                <span>Photo unavailable</span>
              </div>
            }
          />
          {showNavigation ? (
            <button
              className="lightbox-nav lightbox-nav-next"
              type="button"
              onClick={() => move(1)}
              aria-label="Next photo"
            >
              Next
            </button>
          ) : null}
          <span className="lightbox-count" aria-live="polite">
            {activeIndex + 1} of {gallery.length}
          </span>
        </div>
        <footer className="inventory-lightbox-footer">
          <div>
            {active.caption ? (
              <p className="inventory-lightbox-caption">{active.caption}</p>
            ) : null}
            {details.length ? (
              <dl className="inventory-lightbox-details">
                {details.map((item) => (
                  <div key={item.label}>
                    <dt>{item.label}</dt>
                    <dd>{item.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>
          {allowDownload ? (
            <a
              className="ghost lightbox-download"
              href={active.url}
              download
              target="_blank"
              rel="noreferrer"
            >
              Download photo
            </a>
          ) : null}
        </footer>
      </div>
    </div>
  );
}
