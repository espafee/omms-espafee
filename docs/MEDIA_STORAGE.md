# OMMS Media Storage

OMMS image storage is provider-aware so existing Cloudflare R2 images can continue loading while new uploads can be switched to Cloudinary later.

## Current Flow

- Location photos use `MediaSiteImage` through `/api/v1/inventory/site-images/`.
- Advertising Unit photos use `MediaUnitImage` through `/api/v1/inventory/unit-images/`.
- POE proof photos use `ProofOfExecutionMedia` through `/api/v1/poe/media/`.
- Campaign assets currently store external `file_url` values and are not a Django image-upload flow.
- Public campaign pages and the Live Media Planner read the same image records through serializers.

## Providers

- `MEDIA_STORAGE_PROVIDER=r2` keeps the existing Django storage path. Existing records default to `provider=r2` and keep their existing `image` names and URLs.
- `MEDIA_STORAGE_PROVIDER=cloudinary` sends new backend uploads to Cloudinary using `CLOUDINARY_UPLOAD_PRESET=omms_inventory_signed`.
- Cloudinary credentials live only on the backend in `CLOUDINARY_URL`; they are not serialized or exposed to the frontend.
- R2 settings, `USE_S3_MEDIA`, buckets, and credentials must remain configured for legacy images and rollback.

## Cloudinary Metadata

Image records store provider metadata: provider, provider asset ID, public ID, version, secure URL, resource type, format, dimensions, byte size, original filename, primary flag, sort order, uploader, and timestamps. PostgreSQL stores metadata only, not image bytes.

## Folder Layout

New Cloudinary uploads use immutable IDs:

- `omms/tenants/<tenant-id>/locations/<location-id>/`
- `omms/tenants/<tenant-id>/advertising-units/<unit-id>/`
- `omms/tenants/<tenant-id>/poe/<poe-id>/`

The current campaign asset flow is URL-based; do not invent Cloudinary campaign folders until a campaign upload endpoint exists.

## Delivery Variants

Cloudinary records use fixed delivery variants:

- Inventory thumbnail: `c_fill,w_320,h_220,f_auto,q_auto`
- Planner card: `c_fill,w_900,h_600,f_auto,q_auto`
- Full preview: `c_limit,w_1800,f_auto,q_auto`

R2 records continue using their current URLs.

## Upload Safety

Uploads are authenticated, tenant-scoped, and server-side. Accepted formats are JPG, JPEG, PNG, WebP, HEIC, and HEIF, with a 10 MB maximum source size. Cloudinary upload happens before database persistence. If database persistence fails after upload, OMMS attempts to delete the newly uploaded Cloudinary asset.

Replacement uploads the new asset first, updates the database record, then deletes the old Cloudinary asset. Deletion follows the record provider, so Cloudinary records are deleted from Cloudinary and R2 records remain on the R2 path.

## First Deployment Constraint

For the first compatibility deployment, keep production on:

```env
MEDIA_STORAGE_PROVIDER=r2
```

Do not migrate existing images, delete R2 assets, remove R2 credentials, or switch production uploads to Cloudinary automatically.

## Manual Cloudinary Cutover

After the R2-compatible deployment passes checks:

1. Confirm Render already has `CLOUDINARY_URL`, `CLOUDINARY_UPLOAD_PRESET=omms_inventory_signed`, and `CLOUDINARY_ROOT_FOLDER=omms`.
2. Confirm R2 variables and `USE_S3_MEDIA` remain unchanged.
3. Change only `MEDIA_STORAGE_PROVIDER` from `r2` to `cloudinary`.
4. Redeploy the backend.
5. Upload one safe JPG to a test Location or Advertising Unit.
6. Confirm the asset appears in Cloudinary under the expected `omms/tenants/...` folder.
7. Confirm the incoming asset dimensions are limited by the signed preset.
8. Confirm PostgreSQL stores provider metadata and no image bytes.
9. Confirm Inventory thumbnail, full preview, and Live Media Planner image render.
10. Confirm one existing R2 image still renders.
11. Replace and delete only the safe test image, then confirm Cloudinary cleanup behavior.

Rollback is to set `MEDIA_STORAGE_PROVIDER=r2` again and redeploy. Existing Cloudinary test records remain provider-tagged and can still render/delete by record provider as long as Cloudinary credentials remain configured.
