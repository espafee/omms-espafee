import { apiFetch, apiUpload, type UploadProgressHandler } from "@/lib/auth";
import { normalizeMutationError, type InventoryImage } from "@/lib/inventory";

export type SiteImageUploadInput = {
  site: number;
  image: File;
  caption: string;
  is_primary: boolean;
  onProgress?: UploadProgressHandler;
};

export const getSiteImageMutationError = normalizeMutationError;

export async function uploadSiteImage(payload: SiteImageUploadInput) {
  const formData = new FormData();
  formData.append("site", String(payload.site));
  formData.append("image", payload.image);
  formData.append("caption", payload.caption.trim());
  formData.append("is_primary", String(payload.is_primary));

  return apiUpload<InventoryImage>("inventory/site-images/", formData, {
    onProgress: payload.onProgress,
  });
}

export async function updateSiteImage(imageId: number, payload: Partial<Pick<InventoryImage, "caption" | "is_primary">>) {
  return apiFetch<InventoryImage>(`inventory/site-images/${imageId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteSiteImage(imageId: number) {
  return apiFetch<void>(`inventory/site-images/${imageId}/`, {
    method: "DELETE",
  });
}
