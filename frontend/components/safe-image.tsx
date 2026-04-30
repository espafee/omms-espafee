"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

type SafeImageProps = {
  src: string | null;
  alt: string;
  className: string;
  fallback: ReactNode;
  loading?: "lazy" | "eager";
};

export function SafeImage({ src, alt, className, fallback, loading = "lazy" }: SafeImageProps) {
  const [failed, setFailed] = useState(false);
  const isDebugMode = process.env.NODE_ENV !== "production";

  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (!src || failed) {
    if (isDebugMode && src) {
      return <div title={`Failed image URL: ${src}`}>{fallback}</div>;
    }
    return <>{fallback}</>;
  }

  return (
    <img
      className={className}
      src={src}
      alt={alt}
      loading={loading}
      decoding="async"
      onError={() => {
        if (isDebugMode) {
          console.warn("[SafeImage] Failed to load image", { src, alt });
        }
        setFailed(true);
      }}
    />
  );
}
