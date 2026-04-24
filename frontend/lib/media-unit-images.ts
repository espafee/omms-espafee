import { apiFetch } from "@/lib/auth";
import { normalizeMutationError, type InventoryImage } from "@/lib/inventory";

export type MediaUnitImageUploadInput = {
  media_unit: number;
  image: File;
  caption: string;
  is_primary: boolean;
};

export const getMediaUnitImageMutationError = normalizeMutationError;

export async function uploadMediaUnitImage(payload: MediaUnitImageUploadInput) {
  const formData = new FormData();
  formData.append("media_unit", String(payload.media_unit));
  formData.append("image", payload.image);
  formData.append("caption", payload.caption);
  formData.append("is_primary", String(payload.is_primary));

  return apiFetch<InventoryImage>("inventory/unit-images/", {
    method: "POST",
    body: formData,
  });
}

export async function updateMediaUnitImage(imageId: number, payload: Partial<Pick<InventoryImage, "caption" | "is_primary">>) {
  return apiFetch<InventoryImage>(`inventory/unit-images/${imageId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteMediaUnitImage(imageId: number) {
  return apiFetch<void>(`inventory/unit-images/${imageId}/`, {
    method: "DELETE",
  });
}
