# Live Media Planner

Live Media Planner is a controlled client-planning surface, not a public inventory directory. An Admin or Sales user creates a tenant-scoped, expiring link. The client sees only explicitly published units, checks date-aware availability, builds a shortlist, and submits it for formal review.

## Routes

- Internal pipeline: `/sales/proposals`
- Proposal review: `/sales/proposals/{id}`
- Public planner: `/media-planner/{token}`
- APIs: `/api/v1/planner/` and `/api/v1/public/media-planner/{token}/`

## Recent Planner Links

The `Recent planner links` section on `/sales/proposals` shows generated planner links in a compact responsive table. Columns cover planner title/type/pricing, client or company context, eligible/published/excluded inventory counts, status, created/expiry dates when the API provides them, and available actions.

Active links include a `Copy Link` action before Diagnostics and Revoke when the frontend has a safe `public_path` for that link. The action copies the complete public planner URL, shows `Planner link copied`, and briefly changes to `Copied`. Closed, revoked, expired, or otherwise unavailable links do not show the copy action. Active links without a public URL keep the copy action disabled.

Diagnostic warning messages render as a secondary full-width row directly below the affected planner link. On narrow screens, the table stacks each planner row so the title and status remain first, details stay visible, and actions wrap in a full-width footer area.

## Workflow

1. Create a link with optional city, region, format, rate, download, and expiry restrictions.
2. Copy the raw token when it is shown once. OMMS stores only its SHA-256 hash and a short diagnostic prefix.
3. The client selects dates; the backend computes availability.
4. The token-isolated session shortlist creates no booking or hold.
5. Submission stores immutable unit, pricing, tax, and availability snapshots.
6. Internal users review and recheck. Admin/Finance can create an existing OMMS draft estimate.
7. Existing public estimate acceptance/rejection updates the proposal lifecycle.
8. Admin/Sales can convert an approved proposal transactionally. Availability is rechecked and bookings start as `pending`.

`HIDDEN` and the current `CLIENT_RATE_CARD` foundation expose no rate. `STANDARD_SELLING_RATE` exposes only selling rate. A dedicated client rate-card domain remains a future gap.

## Manual Smoke Test

1. Open `/sales/proposals` as Admin or Sales.
2. Create a new secure client link and confirm it appears in `Recent planner links`.
3. On an active link with a public URL, click `Copy Link` and confirm the button changes to `Copied` and the page shows `Planner link copied`.
4. Paste the copied value into a new browser tab and confirm it opens the matching `/media-planner/{token}` public planner.
5. Confirm the Recent planner links table has Planner Link, Client / Company, Inventory, Status, Created / Expiry when available, and Actions columns on desktop/tablet.
6. Confirm the `Copy Link`, `Diagnostics`, and `Revoke` actions stay compact on desktop and wrap cleanly in the mobile stacked row without horizontal overflow.
7. Confirm any tenant mismatch warning appears in a secondary row below the affected planner link.
8. Revoke or close a link and confirm the copy action no longer appears for that link.
9. Confirm any active link without a public URL shows the copy action disabled.
