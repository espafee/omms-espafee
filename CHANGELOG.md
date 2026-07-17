# Changelog

## 2026-07-17

### Fixed
- Fixed inventory site photo upload buttons so the disabled no-file state no longer appears as an uploading/wait state.
- Kept upload loading state scoped to the individual image card and reset only the successful card's file/caption/primary controls.

### Verification
- Added smoke coverage for disabled-before-file, enabled-after-file, upload API call, per-site upload scoping, success refresh, and failure recovery.
