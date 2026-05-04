# OMMS Project Context Handoff

Last updated: 2026-05-04

## Project Identity

OMMS is an Outdoor Media Management System for billboard/outdoor media operations.

Core product areas:
- Inventory: media sites, media units, images, R2 media previews.
- Campaigns: campaign planning, public/client share links, client-facing campaign view.
- Bookings: confirmed placement windows for campaigns and media units.
- POE: proof-of-execution upload, verification, public/client display.
- Billing: campaign estimates, GST-ready invoices, invoice PDFs, private document storage.
- Setup: single-tenant company profile, branding, SMTP settings, setup lock/unlock OTP.
- Mobile: Expo app for field staff POE upload and admin operations overview.

Main repo:
- `C:\Users\Dell\Documents\Codex\omms-project`

Mobile repo:
- `C:\Users\Dell\Documents\Codex\omms-mobile`

Backend:
- Django + Django REST Framework
- JWT auth
- Cloudflare R2-compatible public media storage
- Private R2-compatible document storage for sensitive PDFs/documents

Frontend:
- Next.js App Router
- White + dark forest green SaaS visual direction

## Important Product Rules

- Do not implement multi-tenancy or organization tenancy unless explicitly requested.
- Do not hardcode ESPA FEE, VistaAi, or any client/company data in invoice templates or business logic.
- Keep invoice PDFs private; never store invoices in public media.
- Public campaign links can display campaign/client-facing POE data, but token management stays admin-only.
- Client/user creation must not be public.
- Setup is Super Admin-only and can be locked after final submit.
- Field staff mobile users must never see admin dashboard.
- Booking assignment controls which field staff sees assigned work in mobile.

## Current Git State Warning

As of this handoff, the main repo has uncommitted changes.

These include two groups:
- Earlier cleanup: removed developer/debug/internal UI details from frontend dashboard/page copy.
- Latest invoice work: campaign-level invoice preview/generation from confirmed bookings.

`git status --short` currently shows modified frontend dashboard/setup/campaign/inventory/POE files plus invoice/booking backend files and two new migrations.

If committing only invoice work, stage carefully. If committing all current work, `git add .` will include both the dashboard cleanup and invoice work.

## Recently Completed / In Progress

### 1. Developer-facing dashboard UI cleanup

Visible internal/debug implementation cards were removed or replaced.

Removed/replaced visible copy such as:
- `JWT authenticated`
- `Stored in localStorage`
- `Live API summaries`
- `Dashboard source`
- `Next frontend slice`
- `backend API` wording in user-facing page descriptions

Business-facing replacements include:
- Bookings needing attention
- Inventory in use
- Actions needed
- Neutral role fallback: `Team member`

Files touched include:
- `frontend/app/dashboard/page.tsx`
- `frontend/app/campaigns/page.tsx`
- `frontend/app/inventory/page.tsx`
- `frontend/app/poe/page.tsx`
- `frontend/app/setup/page.tsx`
- `frontend/components/poe-create-panel.tsx`
- `frontend/components/poe-field-capture-form.tsx`
- `frontend/components/safe-image.tsx`

### 2. Campaign-level invoice generation

Business problem:
- Generate Invoice was previously redirecting users toward bookings.
- Invoice generation must not create/re-create bookings.

Implemented direction:
- Generate one campaign-level invoice from existing confirmed bookings.
- Each confirmed booking becomes an invoice line item.
- No redirect to `/bookings`.
- No booking creation during invoicing.
- Duplicate non-cancelled campaign invoices are blocked.

New/updated backend endpoints:
- `GET /api/v1/campaigns/{id}/invoice-preview/`
- `POST /api/v1/campaigns/{id}/generate-invoice/`

Booking cost fields added:
- `agreed_media_cost`
- `flex_cost`
- `installation_cost`
- `other_cost`
- `cost_notes`

Invoice line snapshot fields added:
- `site_name`
- `media_unit_label`
- `booking_start_date`
- `booking_end_date`
- `media_cost`
- `flex_cost`
- `installation_cost`
- `other_cost`
- `cost_notes`

New migrations:
- `apps/bookings/migrations/0004_booking_agreed_media_cost_booking_cost_notes_and_more.py`
- `apps/billing/migrations/0005_invoiceline_booking_end_date_and_more.py`

Frontend billing changes:
- Billing page now selects a campaign.
- User can preview invoice line items.
- User can generate invoice from preview.
- Generate Invoice button calls `POST /campaigns/{id}/generate-invoice/`.
- It does not call `router.push("/bookings")`.

Regression scan result:
- No invoice-related `/bookings` redirect remains in source.
- Only `/bookings` reference found in that scan was the normal sidebar nav link in `frontend/components/app-shell.tsx`.

Important user-facing message:
- `No confirmed bookings found for this campaign. Confirm bookings before generating an invoice.`

### 3. Booking duplicate error cleanup

Booking creation now maps or raises friendlier duplicate booking messages instead of exposing raw Django unique constraint messages such as:
- `The fields campaign, media_unit, start_date, end_date must make a unique set.`

Friendly message:
- `This campaign already has a booking for the selected media unit and date range.`

## Validation Already Run

Backend:
- `python manage.py makemigrations bookings billing` passed.
- `python manage.py migrate` passed.
- `python manage.py check` passed.
- `python manage.py test apps.billing.tests apps.bookings.tests --verbosity 2` passed: 23 tests.
- `python manage.py test apps.billing.tests --verbosity 1` passed: 21 tests.
- Full `python manage.py test` was attempted but timed out after 5 minutes.

Frontend:
- `npm run lint` passed with existing warnings.
- `npm run build` passed with existing warnings.

Existing frontend warnings include:
- React hook missing dependency warnings in older pages.
- Next.js `<img>` optimization warnings.

## Major Implemented Features From This Thread

### Public campaign share links
- Admin can generate/reuse/revoke active share links.
- Existing active links are displayed persistently.
- Public campaign route was stabilized after `.next` cache/build issues.

### Image storage and compression
- Server-side image compression utility exists in `core/images.py`.
- Public media storage supports S3-compatible/R2 storage when enabled.
- Public uploaded image URLs should remain stable across Render redeploys when R2 is configured.

### Private document storage
- Private S3-compatible/R2 document storage exists for invoices/contracts/receipts/internal documents.
- Signed URL helper exists for short-lived private document access.
- Public media storage and private document storage are separate.

### GST invoicing foundation
- `SupplierProfile`
- `InvoiceSequence`
- GST-ready invoice snapshot fields
- Invoice line tax fields
- Invoice issue endpoint
- Controlled invoice numbering: `INV/2025-26/0001`
- CGST/SGST/IGST calculation
- Issued invoices/lines locked from casual edits

### GST invoice PDF generation
- Invoice PDF generation was implemented generically using invoice/supplier snapshot fields.
- PrivateDocumentStorage is used for PDFs.
- Endpoints exist:
  - `POST /api/v1/billing/invoices/{id}/generate-pdf/`
  - `GET /api/v1/billing/invoices/{id}/pdf-link/`
- Do not hardcode any company details in invoice template/code.

### Setup / white-label foundation
- Company profile and organization SMTP settings exist.
- SMTP password is encrypted/write-only.
- Admin setup wizard exists at `/setup`.
- Setup page was redesigned into a SaaS-style admin settings layout.
- Setup can be locked/unlocked with Email OTP.

### Mobile backend APIs
- Field staff assigned work endpoint:
  - `GET /api/v1/mobile/assigned-work/`
- Single request POE submit endpoint:
  - `POST /api/v1/mobile/poe/submit/`
- Mobile admin operations APIs exist:
  - `/api/v1/mobile/admin/overview/`
  - `/api/v1/mobile/admin/running-campaigns/`
  - `/api/v1/mobile/admin/poe-tracker/`
  - `/api/v1/mobile/admin/daily-activity/`
  - `/api/v1/mobile/admin/alerts/`

### Booking assignment system
- `Assignment` model exists.
- Bookings can be assigned to field staff.
- Mobile assigned work now uses assignment logic.

### Issue reporting
- Issue model and APIs exist.
- Public issue report token flow exists.
- SLA/priority fields exist.
- Issue-to-task workflow exists.

## Common Pitfalls For Next Session

1. The old environment path may still mention:
   `C:\Users\Dell\Documents\Codex\2026-04-19-you-are-a-senior-python-backend`

   But the active project folder is:
   `C:\Users\Dell\Documents\Codex\omms-project`

2. If Generate Invoice still redirects in browser:
   - Source scan says no invoice-related `/bookings` redirect remains.
   - Likely cause is stale frontend bundle, old Vercel deploy, or dev server cache.
   - Restart dev server or redeploy Vercel from committed changes.

3. `git add .` currently stages both prior dashboard cleanup and invoice work.

4. Do not remove actual token/localStorage/auth implementation just because visible UI cleanup removed those words.

5. Do not route field staff to admin dashboard in mobile. Use backend role/profile only.

6. Render filesystem media is ephemeral. Production image previews should rely on R2/S3-compatible storage.

## Recommended Next Steps

1. Decide whether to commit all current pending changes together or split them.

Suggested combined commit:
```bash
git status
git add .
git commit -m "Implement campaign-level invoice generation"
```

If splitting commits, stage dashboard cleanup separately from invoice work.

2. Redeploy backend after migrations.

3. Redeploy frontend after committing the billing page changes.

4. Manually verify:
- Billing page stays on `/billing`.
- Select campaign.
- Preview invoice.
- Confirm no confirmed bookings message appears when appropriate.
- Generate invoice from confirmed bookings.
- Browser URL never becomes `/bookings` from Generate Invoice.
- Invoice roster updates.

