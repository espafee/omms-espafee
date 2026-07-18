# Public Inventory Security

## Token boundary

- cryptographically strong URL-safe token, stored only as SHA-256
- tenant-owned, expiring, revocable, and throttled
- no sequential database identifier in public routes

## Public allowlist

The API exposes only opaque unit UUID/code, client-safe location/address, city/region, dimensions, format, facing, illumination, backend availability, approved descriptions/features/media, optional selling rate, and optional verified coordinates.

It never exposes internal database IDs, acquisition costs, margin, internal notes, staff, other tenants, unpublished units, or unrestricted GPS.

Public requests cannot mutate inventory or create bookings. Submission re-resolves token, dates, tenant, and published unit UUIDs before saving server-side snapshots. Token-scoped idempotency prevents normal duplicate requests. Downloads appear only when explicitly granted.
