# OMMS Project Context Handoff

Last updated: 2026-05-11

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

## LATEST SYSTEM STATE (UPDATED)

This section supersedes parts of the earlier handoff where the platform was described more narrowly.

### System Evolution
- OMMS is no longer just an inventory or campaign system.
- OMMS now functions as an:
  - `Outdoor Media Operations & Execution Management System`
- Current core lifecycle:
  - `Campaign Estimate -> Client Approval -> Booking -> Assignment -> POE -> Issue -> Task -> Resolution -> Invoice -> Payment`

### Mobile Apps
- Two mobile roles are implemented:
  - Field Staff
    - Assigned Work
    - POE Upload
    - Issue Reporting
  - Super Admin / Owner
    - Operations Dashboard
    - Running Campaigns
    - POE Tracker
    - Daily Activity
    - Alerts
- Role-based routing is now:
  - backend-driven
  - secure
  - field staff cannot access admin dashboard

### POE System
- Implemented:
  - single-step POE submission API
  - GPS + timestamp capture
  - distance-based validation
  - duplicate POE protection with `409` response
- POE verification statuses:
  - `verified`
  - `suspicious`
  - `failed`

### Issue Reporting System
- Issue system is implemented and linked to booking execution.
- Each `Issue`:
  - is linked to a booking
  - can be reported by field staff or client
  - supports image upload
  - uses lifecycle:
    - `reported -> acknowledged -> in_progress -> resolved`
- SLA tracking exists for:
  - first response timeline
  - resolution timeline
- `sla_status` values:
  - `on_track`
  - `at_risk`
  - `breached`
- Auto-priority exists based on:
  - issue type
  - keywords
  - reporter
  - campaign status
- Client issue reporting is:
  - token-based
  - public
  - no-login
  - limited-data exposure

### Issue -> Task Workflow
- Execution workflow now includes `IssueTask`.
- Each `IssueTask`:
  - is assigned to field staff
  - has due date tracking
  - uses status lifecycle:
    - `pending -> in_progress -> completed`
- Workflow shape:
  - `Issue -> Task -> Assignment -> Execution -> POE -> Auto-resolve`
- Auto-resolution behavior:
  - a new qualifying POE can resolve a related issue automatically
- Overdue handling:
  - tasks past `due_at` are flagged
  - overdue tasks are surfaced in admin alerts

### Booking Assignment System
- `Assignment` is now a core execution concept.
- Meaning:
  - a booking is assigned to field staff
  - this replaces prior reliance on `MediaSite.owner` for field execution ownership
- Impact:
  - mobile assigned work is now accurate
  - POE permissions are tied to assignment

### Billing System Restructure
- Correct business flow is now implemented:
  - `Campaign Estimate -> Client Approval -> Booking -> Invoice -> Payment`
- `Campaign Estimate` is now pre-booking and client-facing.
- Estimate statuses:
  - `draft`
  - `sent`
  - `approved`
  - `rejected`
- Secure public estimate approval flow exists.
- Invoice rules:
  - invoice generation starts only after campaign start date
  - invoice generation is based on confirmed bookings
  - estimate and invoice flows are separated
- Payment tracking now supports:
  - `paid`
  - `partially_paid`
  - `overdue`
- Billing financial dashboard now surfaces:
  - total estimated
  - total approved estimates
  - total invoiced
  - total collected
  - outstanding balance
  - overdue amount

### Invoice PDF UI Review and Redesign
- Latest invoice PDF issue reviewed:
  - old PDF looked too much like a raw ERP export
  - invoice item columns were too cramped for A4 portrait
  - taxable amount and GST percentage could visually merge, for example `25,000.000.00%`
- Premium invoice PDF redesign implemented in `apps/billing/pdf.py`.
- Current PDF layout now includes:
  - company/logo area using setup logo when available
  - prominent `Tax Invoice` header
  - invoice meta section
  - supplier details card
  - bill-to card
  - service/campaign summary card
  - simplified invoice items table
  - separate tax summary
  - highlighted totals card with strong Grand Total
  - amount in words
  - bank/payment details
  - terms and conditions
  - authorised signatory area
  - `Generated by OMMS` footer with page number
- Invoice table was simplified to reduce horizontal pressure:
  - `#`
  - `Description`
  - `Period`
  - `HSN/SAC`
  - `Qty`
  - `Rate`
  - `Taxable`
  - `GST %`
  - `Total`
- CGST, SGST, and IGST remain visible in the separate tax summary and totals card.
- Line item descriptions are now client-friendly:
  - main service title is shown separately
  - site name is shown as its own line
  - media unit is shown as its own line
  - duplicated technical site/unit text is removed from the title where possible
- Empty operational/legal fields now avoid broken `-` display:
  - required fields use `Not Provided`
  - optional empty fields are hidden where possible
- Regression coverage added in `apps/billing/tests/test_gst_invoicing.py` for:
  - invoice PDF section labels
  - no old internal software wording
  - clean wrapped line item descriptions
  - no merged taxable/GST text pattern
- Companion payment-tracking compatibility updates:
  - `apps/billing/serializers.py` now accepts existing payment `method` payloads without requiring duplicate `payment_mode`
  - `apps/users/tests/test_access_control.py` now reflects current `partially_paid` invoice summary behavior after payments exist
- Local PDF review performed:
  - 1-line invoice generated as 1 page
  - 14-line invoice generated as 2 pages
  - merged value pattern was not present
  - old internal wording was not present
  - Grand Total and footer were present

### Admin Mobile APIs
- Admin mobile backend endpoints now include:
  - `/api/v1/mobile/admin/overview/`
  - `/api/v1/mobile/admin/running-campaigns/`
  - `/api/v1/mobile/admin/poe-tracker/`
  - `/api/v1/mobile/admin/daily-activity/`
  - `/api/v1/mobile/admin/alerts/`
- Permissions:
  - admin-only access is enforced at backend

### Branding
- `VistaAi` has been introduced as the parent brand.
- Mobile app branding now reflects:
  - VistaAi parent branding
  - OMMS Mobile product identity
  - role-neutral login screen

### Current Status
- System is now functional across:
  - Web admin
  - Mobile field workflows
  - Mobile admin workflows
  - Backend APIs
- Covered system areas now include:
  - inventory
  - campaigns
  - bookings
  - assignment
  - execution tracking
  - issue detection
  - task workflow
  - billing
  - mobile operations

### Old vs New Context
- Older context in this document is still useful for:
  - repo paths
  - storage architecture
  - GST invoice foundation
  - setup/SMTP/branding foundations
  - earlier invoice-generation decisions
- Newer sections above should be treated as the authoritative description of present system scope and workflow.

## NEXT SYSTEM ENHANCEMENTS

- SLA breach escalation
- task auto-reassignment
- POE image verification improvements
- client estimate approval refinement via public link flows
- payment collection workflows
- analytics dashboard
