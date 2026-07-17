# Changelog

## 2026-07-17

### Added
- Added the All Sites inventory list endpoint at `GET /api/v1/inventory/sites/all-sites/`.
- Added the Inventory page All Sites table with search, filters, pagination, safe thumbnails, and existing view/edit actions.
- Added backend and frontend smoke coverage for the All Sites inventory list.

### Fixed
- Fixed inventory site photo upload buttons so the disabled no-file state no longer appears as an uploading/wait state.
- Kept upload loading state scoped to the individual image card and reset only the successful card's file/caption/primary controls.

### Verification
- Added smoke coverage for disabled-before-file, enabled-after-file, upload API call, per-site upload scoping, success refresh, and failure recovery.

### Documentation
- Documented the endpoint, fields, filters, and manual smoke-test steps for the inventory list.
