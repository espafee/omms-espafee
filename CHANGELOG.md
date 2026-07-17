# Changelog

## 2026-07-17

### Added
- Redesigned Inventory as a URL-backed workspace with Overview, Locations, and Advertising Units tabs; Advertising Units is the default operational view.
- Added `GET /api/v1/inventory/units/all-units/`, a paginated read-only Advertising Unit summary endpoint with parent Location context, filters, image counts, and safe public thumbnails.
- Added focused Location/Advertising Unit detail drawers, a photo-management drawer, and the guided Add Inventory workflow.
- Added the All Sites inventory list endpoint at `GET /api/v1/inventory/sites/all-sites/`.
- Added the Inventory page All Sites table with search, filters, pagination, safe thumbnails, and existing view/edit actions.
- Added backend and frontend smoke coverage for the All Sites inventory list.

### Fixed
- Fixed inventory site photo upload buttons so the disabled no-file state no longer appears as an uploading/wait state.
- Kept upload loading state scoped to the individual image card and reset only the successful card's file/caption/primary controls.
- Removed permanently expanded image upload forms and destructive Location controls from the Inventory workspace lists.

### Verification
- Added smoke coverage for disabled-before-file, enabled-after-file, upload API call, per-site upload scoping, success refresh, and failure recovery.

### Documentation
- Documented the endpoint, fields, filters, and manual smoke-test steps for the inventory list.
