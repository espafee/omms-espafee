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

  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (!src || failed) {
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
        setFailed(true);
      }}
    />
  );
}
