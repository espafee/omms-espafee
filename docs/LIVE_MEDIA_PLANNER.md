# Live Media Planner

Live Media Planner is a controlled client-planning surface, not a public inventory directory. An Admin or Sales user creates a tenant-scoped, expiring link. The client sees only explicitly published units, checks date-aware availability, builds a shortlist, and submits it for formal review.

## Routes

- Internal pipeline: `/sales/proposals`
- Proposal review: `/sales/proposals/{id}`
- Public planner: `/media-planner/{token}`
- APIs: `/api/v1/planner/` and `/api/v1/public/media-planner/{token}/`

## Inventory Counts And Eligibility

The planner counts advertising units and physical locations separately. A physical location can contain multiple advertising units, so a planner can correctly show `23 advertising units across 21 locations`. Operators should not interpret unique location count as missing inventory.

Secure planner eligibility still requires every visible unit to match the planner link tenant, be publicly listed, avoid retired status, and satisfy any allowed city, region, or inventory-type restrictions. Public filters can further reduce the displayed result count, but the public header keeps the eligible advertising-unit count and eligible location count visible. The public planner fetches all paginated result pages instead of stopping at the first 48 records.

The public planner endpoint returns safe count metadata only:

- `meta.eligible_unit_count`
- `meta.eligible_location_count`
- `meta.unique_location_count`
- `meta.results_count`

Detailed reconciliation data is restricted to authenticated platform diagnostics and is not exposed through the public planner.

## Recent Planner Links

The `Recent planner links` section on `/sales/proposals` shows generated planner links in a compact responsive table. Columns cover planner title/type/pricing, client or company context, eligible/published/excluded inventory counts, status, created/expiry dates when the API provides them, and available actions.

Active links include a `Copy Link` action before Diagnostics and Revoke. New planner links retain a copyable `public_path` so the action keeps working after page refresh. The action copies the complete public planner URL, uses the Clipboard API with a textarea fallback, shows `Link copied`, swaps to a check icon, and briefly changes to `Copied`. Closed, revoked, expired, or otherwise unavailable links do not show the copy action. Legacy active links that predate retained public paths cannot be reconstructed from their token hash; clicking Copy Link shows a readable error and operators should create a replacement link if they need copy-from-history.

Diagnostic warning messages render as a secondary full-width row directly below the affected planner link. On narrow screens, the table stacks each planner row so the title and status remain first, details stay visible, and actions wrap in a full-width footer area.

## Diagnostics Reconciliation

Platform Diagnostics on a planner link now shows summary cards for eligible advertising units, unique eligible locations, excluded units, and published inventory inspected. The modal includes Eligible units, Excluded units, and Exclusion summary sections with search and reason filtering.

Excluded rows include the unit code, advertising unit, physical location, city/region, inventory type, operational status, explicit exclusion reason, actual value, and required planner value. Common reasons are `wrong_tenant`, `unpublished`, `retired`, `wrong_city`, `wrong_region`, `wrong_inventory_type`, `invalid_or_missing_location`, `missing_public_id`, `unavailable_for_dates`, and `other`. A unit can carry more than one reason, such as `retired` and `wrong_city`.

If inventory shows 23 published units but a planner shows 21 eligible units, open Diagnostics and check the Excluded units section to identify the exact two unit codes and reasons. If Diagnostics shows 23 eligible advertising units across 21 locations, nothing is missing; two or more units share physical locations.

## Workflow

1. Create a link with optional city, region, format, rate, download, and expiry restrictions.
2. Copy the public link when it is shown. OMMS stores the SHA-256 token hash for validation, a short diagnostic prefix, and the generated public path so authorized internal users can copy active links from Recent planner links after refresh.
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
3. On an active link with a public URL, click `Copy Link` and confirm the button changes to a check-icon `Copied` state and the page shows `Link copied`.
4. Paste the copied value into a new browser tab and confirm it opens the matching `/media-planner/{token}` public planner.
5. Confirm the Recent planner links table has Planner Link, Client / Company, Inventory, Status, Created / Expiry when available, and Actions columns on desktop/tablet.
6. Confirm the `Copy Link`, `Diagnostics`, and `Revoke` actions stay compact on desktop and wrap cleanly in the mobile stacked row without horizontal overflow.
7. Confirm any tenant mismatch warning appears in a secondary row below the affected planner link.
8. Revoke or close a link and confirm the copy action no longer appears for that link.
9. Confirm any active link without a public URL shows the copy action disabled.
10. With test data containing 23 eligible advertising units across 21 physical locations, open the public planner and confirm the summary reads `23 advertising units across 21 locations`.
11. With test data containing 23 published units but 21 eligible units, open Diagnostics and confirm the Excluded units section lists the exact two unit codes and exclusion reasons.
