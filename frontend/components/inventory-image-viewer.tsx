"use client";

import { ImageLightbox } from "@/components/image-lightbox";
import type { InventoryUnit } from "@/lib/inventory";

type InventoryImageViewerProps = {
  unit: InventoryUnit | null;
  initialImageId?: number | null;
  allowDownload?: boolean;
  onClose: () => void;
};

export function InventoryImageViewer({
  unit,
  initialImageId,
  allowDownload = false,
  onClose,
}: InventoryImageViewerProps) {
  if (!unit) return null;
  const images = unit.image_gallery.flatMap((image) =>
    image.image_url
      ? [{ url: image.image_url, alt: `${unit.unit_code}${image.caption ? `, ${image.caption}` : ""}`, caption: image.caption }]
      : [],
  );
  const initialIndex = Math.max(
    0,
    unit.image_gallery.findIndex((image) => image.id === initialImageId),
  );
  return (
    <ImageLightbox
      images={images}
      initialIndex={initialIndex}
      title={unit.unit_code}
      subtitle="Inventory advertising unit"
      details={[
        { label: "Dimensions", value: `${unit.width} x ${unit.height}` },
        { label: "Facing", value: unit.facing_direction || "Pending" },
        { label: "Format", value: unit.site_type.replaceAll("_", " ") },
        {
          label: "Illumination",
          value: unit.is_illuminated ? "Illuminated" : "Standard",
        },
        { label: "Availability", value: unit.status.replaceAll("_", " ") },
      ]}
      allowDownload={allowDownload}
      onClose={onClose}
    />
  );
}
