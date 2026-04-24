"use client";

type ImageLightboxProps = {
  imageUrl: string | null;
  title: string;
  subtitle?: string;
  onClose: () => void;
};

export function ImageLightbox({ imageUrl, title, subtitle, onClose }: ImageLightboxProps) {
  if (!imageUrl) {
    return null;
  }

  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label={title}>
      <button className="lightbox-backdrop" type="button" aria-label="Close preview" onClick={onClose} />
      <div className="lightbox-panel">
        <div className="lightbox-head">
          <div>
            <p className="site-code">Preview</p>
            <h2>{title}</h2>
            {subtitle ? <p className="site-copy">{subtitle}</p> : null}
          </div>
          <button className="ghost" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <img className="lightbox-image" src={imageUrl} alt={title} />
      </div>
    </div>
  );
}
