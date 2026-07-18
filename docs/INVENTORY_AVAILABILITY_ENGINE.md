# Inventory Availability Engine

`InventoryAvailabilityService` is authoritative for planner display and booking writes.

It returns `available`, `partially_available`, `booked`, `on_hold`, `under_maintenance`, or `unavailable` from unit operational/publication state and pending, confirmed, or live bookings. Overlap is inclusive: `existing.start <= requested.end` and `existing.end >= requested.start`.

The planner prefetches relevant bookings into `planner_bookings`, avoiding per-card booking queries. Public queries are tenant-scoped, publication-scoped, paginated, and deterministic. OMMS has no separate maintenance-window model yet, so Phase 1 uses the existing unit maintenance status.
