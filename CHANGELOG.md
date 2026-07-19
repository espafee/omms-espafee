# Changelog

## 2026-07-18

### Added
- Added a secure rolling 72-hour inactivity session model using short-lived access tokens and HttpOnly refresh-session cookies.
- Added a `Copy Link` action to active Recent planner link cards on `/sales/proposals`, placed before Diagnostics and Revoke.
- Recent planner links now copy their complete public `/media-planner/{token}` URL when a safe public path is available, show `Link copied`, and briefly switch the button label to `Copied`.
- Redesigned Recent planner links as a compact responsive table with planner, client/company, inventory, status, dates when available, and action columns.

### Fixed
- Fixed Recent planner link copying for page reloads by persisting and listing the copyable planner `public_path` for newly generated links.
- Active legacy planner links without a retained public URL now show a clear copy error instead of presenting a dead-feeling disabled action.
- Fixed the Recent planner links `Copy Link` action so it copies exact public planner URLs, falls back safely when the Clipboard API is unavailable, shows `Link copied` with a temporary check-icon `Copied` state, and recovers with a readable error if copying fails.
- Fixed frequent automatic logout by queuing silent refresh attempts, retrying expired-access requests once, and avoiding auth clearing on temporary refresh network failures.
- Closed, revoked, expired, and unavailable planner links no longer show the Recent links copy action.
- Active planner links without a public URL now render the copy action disabled instead of attempting an invalid clipboard write.
- Moved planner diagnostics warnings into full-width secondary table rows so warnings do not crowd narrow action cells.
- Fixed Inventory Add/Edit modal stacking so global search and filter controls stay behind the backdrop and cannot overlap the dialog.

### Documentation
- Documented Live Media Planner recent-link copy behavior and manual smoke-test steps.

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
