# ADR 0001: Separate Location and Advertising Unit inventory experiences

## Status

Accepted, 2026-07-17.

## Context

The existing Inventory page combined site creation, media-unit creation, list data, complete galleries, image upload forms, and deletion controls in one long surface. That made it difficult to distinguish a physical advertising place from a sellable face and caused photo-management controls to dominate the operational workflow.

The existing domain model is authoritative and already supports the required hierarchy: `MediaSite` has many `MediaUnit` records. Bookings, campaigns, POE, billing, tenant scoping, public campaign previews, safe public image URLs, and permission rules already depend on those models and their identifiers.

## Decision

Keep the domain model and API identifiers unchanged. Use **Location** as the UI label for `MediaSite` and **Advertising Unit** for `MediaUnit`.

The Inventory page is a URL-backed workspace with Overview, Locations, and Advertising Units tabs. Advertising Units is the default list because it is the sellable and operational surface. Locations list only physical-place data. Detail and photo-management interactions use drawers so forms and galleries are not rendered for every row.

The existing site list remains the Location summary endpoint. A paginated, read-only `/inventory/units/all-units/` action exposes unit summaries with parent Location context. It uses the same tenant-scoped source of truth and safe public media URL builder as existing inventory endpoints.

## Consequences

- Existing records, `MediaSite`/`MediaUnit` relationships, booking/campaign/POE/billing links, public image behavior, and server-side permissions remain compatible.
- No migration is required and existing codes are not renamed.
- List pages can paginate records and defer galleries until a user asks to manage photos.
- Admin-only Location creation/deletion and operations/admin Unit and photo management continue to be enforced by the backend.
- The Add Inventory flow creates Location and Unit records sequentially with the existing APIs. It intentionally does not introduce a schema-level bulk-create contract.
