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

### Invoice PDF Final Polish Pass
- Latest invoice PDF polish pass completed after reviewing leftover visual issues.
- Improvements made:
  - reduced awkward top whitespace with a tighter header
  - removed duplicate invoice number from the top header
  - made invoice metadata dynamic so optional empty fields are hidden
  - removed repeated `Not Provided` placeholders from client-facing PDF output
  - ensured supplier card shows actual configured supplier/company name
  - redesigned campaign summary into a natural wrapping 2-column card
  - widened invoice description and HSN/GST columns to prevent label/value wrapping issues
  - kept `GST %` and `HSN/SAC` readable without splitting
  - improved totals spacing and Grand Total highlight
  - changed amount-in-words into a compact highlighted strip
  - normalized bank labels to `Account Holder`, `Account Number`, `IFSC`, and `Branch`
  - changed signature block to `Authorised Signatory` and `For <company name>`
  - changed footer to `Generated by OMMS | Page X of Y`
- Local PDF review after polish:
  - ESPA-style 1-line sample generated as 1 page
  - 14-line sample generated as 2 pages
  - no `Not Provided` placeholder spam
  - no repeated `Invoice No.` header label
  - no merged taxable/GST value pattern
  - bank details and signature block extracted cleanly

### Invoice GST Calculation Fix
- Critical GST issue fixed after invoice PDFs showed `GST %` as `0.00%`.
- Root cause:
  - campaign-level invoice generation explicitly passed `gst_rate=0.00`
  - this bypassed configured tax/rate-card data and produced misleading zero-tax invoices
- Corrected GST rate resolution now checks:
  - explicit invoice/API GST rate if provided
  - media unit `RateCard.tax_percentage` for the booking window
  - optional billing settings such as `BILLING_DEFAULT_GST_RATE` / `BILLING_GST_RATE_BY_SAC`
- GST-registered suppliers now require a configured GST rate before taxable invoice lines can be issued.
- Campaign-generated invoices now auto-use the active supplier profile where available.
- Tax split logic now supports:
  - CGST + SGST for same supplier/place-of-supply state
  - IGST for different states
  - state-name fallback when state codes are unavailable
- PDF behavior updated:
  - GST invoices show correct GST %, CGST/SGST/IGST, tax summary, and GST-inclusive Grand Total
  - non-GST invoices hide GST-specific line columns and show a non-GST tax status note
- Acceptance verification performed:
  - taxable amount `50000.00`
  - configured GST `18.00%`
  - CGST `4500.00`
  - SGST `4500.00`
  - total GST `9000.00`
  - grand total `59000.00`

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

### Production Hardening Milestone
- A full production-readiness hardening pass was started after the quality/endurance audit.
- Highest-priority changes covered:
  - frontend Next.js security patch within the 14.x line
  - DRF throttling for login/token, OTP, public token links, public issue reporting, and upload surfaces
  - public self-registration disabled by default with explicit environment opt-in
  - invoice listing/summary made side-effect-free while preserving explicit payment-status refresh after payments and scheduled jobs
  - POE duplicate protection refined to allow controlled replacement after rejected/suspicious POE or a newer open issue
  - public issue token APIs changed to unauthenticated frontend fetches so stale JWTs cannot break public links
  - mobile app cleanup for invalid Android config, release console logs, role routing, and access-token refresh
  - Python runtime standardized around `python-3.11.9`
- Operational configuration now documents:
  - `OMMS_PUBLIC_REGISTRATION_ENABLED`
  - DRF throttle-rate environment variables
  - `BILLING_DEFAULT_GST_RATE`
  - `BILLING_GST_RATE_BY_SAC`
  - production security reminders for HTTPS, cookies, CSRF/CORS, and HSTS

### Billing Hardening + POE GPS Workflow Sprint
- Latest production-readiness sprint tightened billing, invoice PDF, payment handling, and site GPS behavior.
- Billing/payment changes:
  - `Record Payment` action now moves the user directly to the selected invoice payment panel
  - payment amount is prefilled from balance due
  - frontend validates amount, date, payable invoice state, and overpayment before submit
  - backend rejects draft/cancelled/paid invoice payments and prevents overpayment
  - invoice payment status refresh remains explicit after payment writes, not on list/read paths
- Invoice PDF corrections:
  - PDF display now prefers configured company profile/setup data for header, supplier, bank account holder, and signature company
  - optional missing placeholders such as `-` and `Not Provided` are suppressed
  - bank labels normalize to `Account Holder`, `Account Number`, `IFSC`, and `Branch`
  - GST calculation remains driven by configured invoice/rate-card/SAC/default tax source, with validation when a GST-registered invoice has no rate
- Site GPS strategy:
  - inventory site latitude/longitude remain optional at creation
  - frontend helper text explains that coordinates are auto-captured during first verified POE
  - site location lifecycle fields added:
    - `location_status`: `unverified`, `provisional`, `verified`, `suspicious`
    - `location_source`: `manual`, `first_verified_poe`, `admin_verified`
    - `location_verified_at`
    - `location_verified_by`
  - first POE with GPS stores provisional coordinates if site has none
  - verified first POE locks site coordinates with source `first_verified_poe`
  - future POEs validate distance from locked coordinates without overwriting them
  - admin coordinate updates are treated as admin-verified overrides
- Targeted verification added for:
  - payment overpayment/draft invoice rejection
  - full payment status transition
  - company-profile-driven PDF supplier/bank/signature display
  - site creation without coordinates
  - first POE GPS capture and lock
  - near/far future POE validation against locked coordinates

### Finance Audit + POE Review Readiness Sprint
- Latest operational-readiness sprint added finance auditability and POE review polish.
- Billing/finance additions:
  - selected invoice payment history now shows all recorded payments with date, amount, method, reference, notes, and recorded-by user
  - invoice lifecycle has guarded transitions for draft, issued, partially paid, paid, overdue, and cancelled/void states
  - invoice cancellation/void endpoint requires a reason and blocks invoices that already have payments
  - invoice audit events track created, issued, PDF generated/downloaded, payment recorded, status changed, and voided events
  - client statement endpoint/UI summarizes total billed, total paid, outstanding balance, unpaid invoices, and payment history
  - dashboard finance widgets now include due-soon invoices, overdue invoices, payments received this month, and draft invoice count
- POE review additions:
  - POE API exposes location confidence with captured GPS, distance, threshold, radius result, and site location status
  - web POE review queue now supports campaign, site, field agent ID, status, suspicious-only, and date range filters
  - operations/admin users can quick approve or reject POE records when safe
- Notification hooks now create internal event-ready logs for:
  - invoice issued
  - payment recorded
  - suspicious POE detected
  - client/field issue reported
- QA documentation:
  - `QA_SMOKE_TEST_CHECKLIST.md` documents manual smoke steps and expected results for login, setup, inventory, campaign, booking, estimate, invoice, payment, PDF, POE, issue reporting, and public links.

## NEXT SYSTEM ENHANCEMENTS

- SLA breach escalation
- task auto-reassignment
- POE image verification improvements
- client estimate approval refinement via public link flows
- payment collection workflows
- analytics dashboard

## Operational Intelligence + Observability Foundation Sprint

- Added a central `apps.observability` module for safe SaaS operations telemetry.
- API request logging:
  - logs API method, path, status, duration, user, company snapshot, category, IP/user-agent, and slow flag
  - slow threshold is controlled by `OMMS_SLOW_REQUEST_MS`
  - request bodies, auth headers, OTPs, tokens, passwords, and uploaded files are not logged
  - admin can filter slow requests in Django admin and via API
- Central audit timeline:
  - `AuditEvent` tracks event type, entity type/id, actor, company, severity, summary, safe metadata, and references
  - invoice events, POE upload/review, site GPS lock, public issue reporting, and issue escalation now write central audit entries
- Notification center:
  - internal `Notification` inbox added alongside existing email notification logs/preferences
  - `/notifications` page lists alerts, supports unread filtering, severity filtering, and mark-read action
- Operations intelligence page:
  - `/operations` shows suspicious POE counts, missing GPS, geofence misses, overdue review counts, recent suspicious POE drill-down, diagnostics, and audit timeline
- POE upload reliability:
  - `client_upload_id` added for safe retry/idempotency
  - repeated POE create calls with the same upload ID return the existing record instead of creating duplicates
- Import/export foundation:
  - `ImportExportJob` tracks review-first import/export jobs
  - inventory site CSV export and import preview validation added
- Dashboard performance:
  - campaign, booking, and billing dashboard summaries now use user/role-scoped cache keys
  - mutation paths bump a dashboard cache version for short-lived aggregate invalidation
- Background jobs:
  - Celery-ready tasks added for notification retry, invoice status refresh, and request-log cleanup
  - `cleanup_api_request_logs` management command added
- New documentation:
  - `OBSERVABILITY_OPERATIONS.md` documents request logging, audit timeline, notifications, POE analytics, diagnostics, background jobs, upload idempotency, import/export, and caching.

## Production Operations Foundation Sprint

- Deployment health checks:
  - public `/health/` endpoint added for Render/web uptime checks
  - admin diagnostics now include background job flag, recent critical alerts, and notification retry health without exposing secrets
- Celery/Beat production wiring:
  - Beat schedule now covers request-log cleanup, notification retry queue, invoice status refresh, and alert threshold evaluation
  - documented worker and beat commands for Render services
  - background jobs remain optional for normal local web startup
- Alert thresholds:
  - `AlertRule` and `AlertEvent` added
  - threshold evaluator covers slow requests, failed notifications, suspicious POEs, overdue POE reviews, breached issues, and overdue invoices
  - cooldown logic prevents duplicate alert spam
  - alert events create audit entries and internal operations notifications
- Import/export:
  - inventory site import now has a safe preview-only foundation
  - duplicate site codes, repeated rows/media unit codes, invalid pricing/dimensions, missing required fields, and suspicious coordinates are detected during preview
  - confirmation/background processing remains intentionally disabled until the next import workflow phase
  - CSV exports added for campaigns, invoices, POE reports, client statements, and inventory sites
- Operations UI:
  - `/operations` now includes filters, compact bar charts, alert cards, diagnostics, import preview cards/tables, disabled Start Import placeholder, and export actions
- Notification preferences:
  - preferences now support `in_app_enabled` and `email_enabled`
  - notification center exposes event-type preferences and respects in-app opt-outs for user-targeted notifications
- New documentation:
  - `CELERY_BACKGROUND_JOBS.md`
  - `IMPORT_EXPORT.md`
  - `DEPLOYMENT_HEALTHCHECKS.md`

## Finance Controls + Audit Review + Smoke Test Sprint

- Latest sprint expands finance controls from payment recording into controlled void/refund handling.
- Credit note/refund workflow:
  - paid or partially paid invoices can now be voided only with a reason plus credit/refund amount, date, method, reference, and notes
  - payment history is preserved; payments are never deleted during voiding
  - credit/refund records are linked to the invoice and logged in invoice audit events
- Invoice detail workflow:
  - billing dashboard links each invoice to a dedicated invoice detail page
  - invoice detail shows metadata, line items, payment history, credit notes, audit trail filters/search, PDF action, record payment, and void controls
  - billing dashboard remains a roster/workbench instead of expanding all audit information inline
- Client statement exports:
  - client statement can now be exported as CSV or PDF
  - exports include invoice rows, payment rows, balances, and credit/refund rows where present
- Notification readiness:
  - notification logs now include issue links, retry count, last attempt, and next retry timestamp
  - user notification preferences allow event-level email enable/disable
  - issue escalation notification event added
- Issue escalation/audit:
  - high-priority/SLA-breached issues can escalate automatically
  - admin users can manually escalate issues with a reason
  - issue events record reported, escalated, task assigned, and auto-resolved milestones
- POE review SLA:
  - POE records now track review due date, reviewed timestamp, reviewer comment, and SLA status
  - POE review queue shows SLA badges and reviewer comments
- Finance permissions:
  - granular finance permission checks now protect invoice issue, payment recording, voiding, statement export, and finance dashboard access
  - clients remain scoped to their own finance data
- Dashboard drill-downs:
  - finance widgets deep-link to billing filters for unpaid, overdue, due-soon, draft invoices, and payments this month
- Automated smoke testing:
  - Playwright smoke setup added under `frontend/e2e/smoke`
  - tests verify public/protected routes and invoice detail deep-link route respond without server errors
- Test architecture isolation:
  - Django `manage.py test` defaults to backend `apps` discovery through `core.test_runner.BackendOnlyDiscoverRunner`
  - `pytest.ini` excludes frontend, node, build, Playwright, media, and static artifact folders
  - Playwright reports, traces, videos, screenshots, and test results are frontend-scoped and gitignored
  - `TESTING.md` documents backend, frontend, and E2E commands as separate phases

## Responsive UI Polish For VistaAi Embed

- OMMS app shell was tuned for laptop and desktop embeds so dashboards can use wider available screens instead of feeling boxed inside a narrow viewport.
- Dashboard shell now has a wider maximum working area, fluid sidebar width, safer content min-width handling, and responsive summary cards.
- POE recent evidence images now cap their visual height and use contained image rendering, reducing oversized media cards on MacBook/laptop screens.
- This supports the VistaAi `/omms/login` iframe wrapper, which was widened to better use 16-inch MacBook Pro and desktop browser widths.

## VistaAi Portal Login Signal

- OMMS frontend login now sends a safe parent-window login signal when used inside the VistaAi `/omms/login` iframe.
- The VistaAi website uses this signal only for UX, allowing marketing navigation to show `Open App` after a successful embedded login.
- The actual secure OMMS authentication remains inside the OMMS app JWT flow; VistaAi does not read or store the JWT.

## Website QA And Training Module Sprint

- In-app Training and Help Center added at `/training` for authenticated OMMS users.
- Sidebar navigation now includes `Training` with stable Playwright test selectors across all major modules.
- Training module publishes the master OMMS manual plus role-based PDF guides from `frontend/public/training`.
- Role-based guide visibility is future-ready:
  - admins, super admins, and owners can see all guides
  - field, finance, operations, and inventory users see their relevant training material
- Playwright smoke coverage expanded for:
  - login invalid/success handling
  - protected workflow routes
  - sidebar navigation coverage
  - Training page access
  - Training PDF availability
  - unauthenticated Training redirect
- QA focus for this sprint:
  - verify no broken Training routes or PDF links
  - keep Training access inside the authenticated OMMS app
  - preserve existing billing, campaign, booking, POE, operations, and notification workflows

## POE Review UI Alignment

- POE recent evidence now uses dedicated compact media-review cards instead of the generic asset-card stack.
- The right-side evidence panel keeps proof thumbnails at a uniform 4:3 ratio, places captured date/time first, then site/unit, executed date, proof link, and status, and keeps verified badges aligned without overlapping image content.
- The persistent signed-in banner shown above the embedded dashboard is owned by the VistaAi TrustDial wrapper, not the OMMS frontend. The wrapper should be deployed together with this OMMS frontend update so the temporary toast behavior is visible in the embedded `/omms/login` experience.

## Inventory Import Preview Foundation

- Inventory imports now start with a preview-only flow in the Operations import/export workbench: upload CSV/Excel, parse rows, validate data, and show summary counts before any inventory records are committed.
- Preview validation detects missing site fields, invalid site/unit choices, repeated rows, repeated media unit codes, existing site/unit duplicates, suspicious coordinates, invalid pricing, and invalid dimensions.
- Latitude/longitude remains optional because OMMS GPS is captured from the first verified POE; missing coordinates produce a warning, not a failed row.
- `ImportExportJob` stores the preview reference, normalized row data, row-level warnings/errors, duplicate handling notes, and a `no_records_imported` flag for the next confirmation phase.
- Frontend UX shows compact summary cards, warning/error lists, preview rows, duplicate counts, and the explicit message `No records have been imported yet` before confirmation.

## Inventory Import Confirmation And Background Processing

- Previewed inventory imports can now be explicitly confirmed with a `confirmed: true` request; non-previewed, cross-company, already completed/running, and empty-preview jobs are rejected.
- Confirmed jobs move to `confirmed` as the queued state, then process through `process_inventory_import_job` when Celery is available; local/eager fallback processing remains safe for development and tests.
- Processing imports only preview-ready rows, skips failed preview rows, updates existing sites only when preview marked the row as update-safe, skips existing media units, and writes partial-success result counts back to `ImportExportJob`.
- `ImportExportJob` now tracks imported, updated, skipped, failed, started, completed, duration, progress, processed row states, and an optional CSV error report.
- Completion/failure writes audit events and creates the `Inventory import completed` operations notification with summary counts.
- Operations UI now enables `Start Import` for importable previews, requires a confirmation modal, polls queued/running jobs, and shows final imported/updated/skipped/failed/duration counts.

## Export System Expansion Phase 1

- Core operational exports now run through `ImportExportJob` instead of one-off synchronous responses.
- CSV export coverage includes inventory sites, campaigns, POE reports, and invoice/payment rows; client statements remain supported through the same export processor.
- Export jobs start in `confirmed` as the queued state, move to `processing`, then finish as `completed` or `failed`; progress, started/completed timestamps, duration, row counts, output file, and safe errors are tracked on the job.
- `process_export_job_task` handles Celery execution; local/eager fallback generation remains available when background dispatch is unavailable.
- Completion/failure writes audit events, and successful exports create an `Export completed` operations notification.
- Operations UI now has an export type selector, optional status filter, Start Export action, recent export job list, progress chips, and download links for completed CSV files.

## Operations Intelligence Dashboard Enhancements Phase 1

- `/operations` now opens as an operational intelligence dashboard rather than only a raw tools page.
- The operations summary API returns compact KPI cards, chart-ready aggregate datasets, a unified operational timeline, and a lightweight system health panel.
- Filters now support date range, company/tenant, status, module/type, severity, user role, campaign, inventory/site, and notification type where the underlying data supports safe scoping.
- Dashboard analytics cover import/export activity, failed and slow request trends, POE status/reviewer workload, billing and payment activity, notification volume, audit activity, and operational load distribution.
- The unified timeline merges audit events, import/export jobs, and POE review signals with module/status badges, actor labels, and timestamps.
- System health summarizes Celery mode, broker configuration, active/failed jobs, API failure rate, retry backlog, and the last successful import/export without requiring Render shell access.

## Notification Preferences UI

- Notification preferences now cover the operational categories needed by current SaaS workflows: import completed/failed, export completed/failed, POE suspicious/rejected/approved, invoice/payment, system diagnostics, and campaign alerts.
- The preferences API returns grouped event metadata so the frontend can render category labels and short descriptions without hard-coding display-only business meaning.
- `/notifications` now includes a compact grouped preferences panel with Inbox and Email toggles per category, save success/error feedback, and no change to existing inbox history.
- In-app preferences now filter role-based inbox notifications for the current user, so muted operations categories do not continue appearing through shared role notifications.
- Preference list reads default to the current user; privileged users can still query another user explicitly through the existing `user` filter.

## Alert Thresholds Phase 1

- The existing observability alert foundation now covers Phase 1 operational risk metrics: failed import/export jobs in 24h, suspicious POEs in 24h, overdue invoices, failed API requests in 24h, and slow API requests.
- Alert evaluation remains Celery-ready through `evaluate_operational_alert_thresholds` and creates `AlertEvent`, `AuditEvent`, and operations inbox notifications when thresholds breach.
- Cooldown protection prevents duplicate alert events and notifications for the same rule within the configured cooldown window.
- Alert rules expose current value, threshold, enabled state, window, cooldown, severity, and last triggered time through the alert-rules API.
- `/operations` now includes an Alert thresholds section; admins can enable/disable rules and adjust threshold values, while operations/finance users can view the risk state.

## Operational Alert Acknowledgement Milestone

- Alert events now support explicit acknowledgement through `POST /api/v1/observability/alert-events/{id}/acknowledge/`.
- Acknowledgement records who acknowledged the alert and when, then writes an `alert.acknowledged` audit event for operational traceability.
- Alert rule API responses now include cooldown visibility (`cooldown_until` and `cooldown_remaining_minutes`) so operators can understand when the next notification for that condition can fire.
- The Operations dashboard now shows acknowledgement state, acknowledgement actor/time, compact severity actions, and cooldown remaining text inside the alert sections.
- Mobile parity review: current mobile admin alerts are synthetic field-operation alerts, not persisted `AlertEvent` records. No mobile API contract was changed in this milestone; mobile already uses matching warning/danger alert severity visuals from the OMMS mobile theme.

## Operational Auto-Refresh And Live Activity Layer

- `/operations` now runs a calm live-refresh loop for operational summary, alerts, timeline, audit events, export jobs, notification counters, and dashboard health.
- The default dashboard refresh interval is 45 seconds, with request de-duplication and automatic pause while the browser tab is hidden.
- Active import/export jobs still refresh more frequently while queued or processing, now at a less aggressive 5-second interval.
- A compact live strip shows `Live`/`Paused`, last updated relative time, active job count, export queue count, and a subtle refresh pulse without reloading the page.
- The import/export workbench now includes an active background job monitor for import queue, export queue, and last completed export.
- Mobile parity: the mobile admin operations dashboard now has a lightweight 60-second refresh loop while the app is active. Field assigned-work remains manual refresh to avoid unnecessary battery/network usage for field staff.

## Failed Import/Export Retry Workflow

- Failed `ImportExportJob` records can now be retried through `POST /api/v1/observability/import-export-jobs/{id}/retry/`.
- Retry is allowed only for failed jobs and creates a linked retry job through `retry_of`, preserving the original failed job, failed report, retry count, and last retry time.
- Inventory import retries reuse the saved preview metadata and existing idempotent import processing, so already-created sites/units are skipped rather than duplicated.
- Export retries reuse the original export filters and regenerate the output CSV through the same background-safe export processor.
- Retry requests create audit events (`inventory.import.retry_requested` or `export.retry_requested`); retry completion/failure uses existing import/export notifications, including failed export notifications.
- The Operations dashboard now shows retry metadata and Retry actions for eligible failed import/export jobs.
- Mobile parity review: mobile admin remains read-only for operational job control. Retry actions stay web-only because they mutate import/export state and require the richer Operations workbench context.

## POE SLA Breach Indicators And Reviewer Workload

- POE review risk now has explicit SLA states: pending reviews warn after 24 hours and breach after 48 hours; suspicious or rejected unresolved POEs warn after 12 hours and breach after 24 hours.
- SLA thresholds are environment-configurable through `OMMS_POE_REVIEW_WARNING_HOURS`, `OMMS_POE_REVIEW_BREACH_HOURS`, `OMMS_POE_SUSPICIOUS_WARNING_HOURS`, `OMMS_POE_SUSPICIOUS_BREACH_HOURS`, and `OMMS_POE_REVIEWER_OVERLOAD_THRESHOLD`.
- POE API responses now include a computed `sla_indicator` payload with status, label, age, warning time, breach time, and suspicious-unresolved flag while preserving the existing `review_sla_status` field.
- Operations summary now includes POE SLA warning/breach KPIs, oldest pending POE, unassigned review backlog, suspicious unresolved count, and reviewer workload distribution with pending/approved/rejected/rework counts.
- Alert thresholds now include the `poe_sla_breaches` metric, creating audit events and operations notifications when breached POE reviews exceed the configured rule.
- Mobile parity review: field staff do not see reviewer workload. Mobile admin overview receives only high-level POE SLA warning/breach KPIs to keep the app lightweight.

## Invoice Overdue Escalation And Collection Analytics

- Billing intelligence now calculates overdue invoice count/value, collection efficiency, pending/collected/invoiced totals, average days to payment, payment trend, overdue age buckets, and top overdue clients.
- Invoice API responses now include a computed `escalation_status` with `due_soon`, `overdue_warning`, `overdue_breach`, `critical_overdue`, or `settled` labels without changing invoice lifecycle writes.
- Operations summary exposes billing risk only to admin/finance users; operations users keep operational visibility but do not receive client-level receivables exposure.
- The existing `overdue_invoices` alert metric now uses effective due-date/balance calculations instead of relying only on stored invoice status, and overdue alerts notify admin and finance role inboxes in addition to the operational alert trail.
- `/operations` adds overdue invoice/value KPIs, collection efficiency, overdue age buckets, payment trend, and top overdue clients. `/billing` adds escalation badges and payment-risk hints to invoice rows.
- Mobile parity: mobile admin overview receives high-level overdue invoice count, overdue value, and collection efficiency KPI cards. Field staff mobile screens remain finance-free.

## Campaign Performance Analytics Foundation

- Campaign analytics now calculate active campaigns, campaigns ending soon, booked site count, approved/pending/missing POE sites, POE completion percentage, suspicious POE count, invoice generated status, payment completion percentage, overdue invoice presence, operational delay indicators, billing status, payment collection status, and campaign risk classification.
- Risk classification is analytics-only and does not mutate campaign lifecycle status. Computed values are `on_track`, `needs_attention`, `poe_risk`, `billing_risk`, and `critical`.
- Billing-sensitive campaign fields are hidden for non-admin/non-finance users while operational POE risk remains visible to operations roles.
- Operations summary now includes campaign ending-soon, POE risk, billing risk, critical campaign count, risk distribution, POE completion trend, operational health trend, and a compact campaign performance list.
- Alert thresholds now include `campaigns_at_risk`; critical campaign risk creates alert/audit records and notifies admin and operations inbox roles with existing cooldown protection.
- `/campaigns` now shows performance badges/cards for POE completion, missing POE, risk status, billing status, and overdue exposure where permitted.
- Mobile parity: mobile admin overview receives high-level active campaign, campaigns-at-risk, campaigns-ending-soon, and critical campaign KPIs. Field staff screens remain focused on assigned execution work.

## Global Operational Search And Saved Views Foundation

- Observability now owns a lightweight global operational search endpoint at `GET /api/v1/observability/operational-search/`.
- Search covers campaigns, POEs, import/export jobs, alerts, audit events, notifications, sites/media units, and finance/client records where the caller has the appropriate role.
- Phase 1 search uses simple indexed ORM filters, per-module limits, and result caps instead of Elasticsearch/OpenSearch. Finance and client search results are hidden from non-admin/non-finance users.
- Saved operational views are persisted in `SavedOperationalView`, scoped to the current user and company name, and exposed through `/api/v1/observability/saved-views/`.
- `/operations` can save and restore filter combinations such as critical campaigns, failed imports, pending POEs, finance risk, or daily operations.
- The shared app shell now includes a compact operational search dropdown with grouped results and recent local searches.
- Mobile parity: mobile admin gets a lightweight campaign/site/unit lookup at `GET /api/v1/mobile/admin/search/`. Field staff search remains limited to assigned work context; no finance or operational intelligence search is exposed to field users.

## Role-Based Dashboard Customization Foundation

- Observability now exposes `GET/PATCH/POST /api/v1/observability/dashboard-profile/` for role-aware dashboard profiles, widget preferences, and restoring defaults.
- Default widget sets are defined for admin/owner, operations, finance, field staff, and client roles.
- Persisted `DashboardWidgetPreference` rows are scoped by user and company name and store widget visibility plus sort order.
- The main dashboard reads the profile before loading summaries, so finance summaries are only requested when the active role can view finance widgets.
- Back-office roles can hide/show safe optional widgets from the dashboard. Field staff and client dashboards remain default-guided to avoid exposing admin customization or operational intelligence.
- Security behavior: finance widgets are blocked for operations/field users, operations-intelligence widgets are blocked for clients/field users, and required field/client widgets cannot be hidden.
- Mobile parity: no heavy mobile customization was added. Mobile admin remains a focused operational companion, and field staff mobile stays centered on assigned work and POE upload.
