# Live Media Planner

Live Media Planner is a controlled client-planning surface, not a public inventory directory. An Admin or Sales user creates a tenant-scoped, expiring link. The client sees only explicitly published units, checks date-aware availability, builds a shortlist, and submits it for formal review.

## Routes

- Internal pipeline: `/sales/proposals`
- Proposal review: `/sales/proposals/{id}`
- Public planner: `/media-planner/{token}`
- APIs: `/api/v1/planner/` and `/api/v1/public/media-planner/{token}/`

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
