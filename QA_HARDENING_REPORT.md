# OMMS QA Hardening Report

Generated: 2026-05-20

## Scope

This pass focused on stabilization, hardening, workflow integrity, reliability, security posture, deployment readiness, and mobile readiness. No new product features were introduced.

## Code Hygiene Fixes Applied

- Removed tracked generated development artifact: `frontend/tmp_login.html`.
- Removed mobile runtime auth/profile logging from:
  - `src/api/auth.ts`
  - `src/App.tsx`

These changes reduce source noise and avoid auth/profile routing details appearing in production device logs.

## Workflow Integrity Review

Reviewed and validated existing coverage for:

- Campaign, booking, billing, invoice, payment, and POE workflows.
- Import preview/confirmation and export background jobs.
- Failed import/export retry state and idempotency tests.
- Alert thresholds, cooldowns, notifications, preferences, and escalation-related issue workflows.
- Dashboard customization and dynamic widget rendering.
- Maintenance/read-only operational mode.
- Training document access and download routing.

Automated validation passed for the current suite. Additional real-world UAT is still recommended for full campaign lifecycle from estimate approval through payment and POE completion with production-like media assets.

## Endurance And Resilience Findings

Validated by automated tests and smoke checks:

- Operations dashboard can render without global audit refresh errors.
- Dashboard widget customization can hide/show/restore sections.
- Diagnostics and Operations summary failure paths return safe fallback responses.
- Import/export job status and retry behavior have backend coverage.

Recommended endurance tests before broad launch:

- Repeated Operations dashboard polling for 2-4 hours with production telemetry enabled.
- Repeated import preview/confirm/retry cycle using mixed valid/invalid/duplicate rows.
- Repeated export generation and download checks for each export type.
- Celery worker restart during queued/running import/export jobs.
- Mobile repeated POE upload on weak network and after foreground/background transitions.

## Security Findings

No direct secret exposure was found in source during this pass.

Important guardrails already present:

- Production secret-key enforcement.
- Role-aware API and dashboard visibility.
- Finance data restricted to authorized roles.
- Client and field staff surfaces constrained.
- Observability metadata redaction.
- Throttle rates for auth, public links, setup, and uploads.

Pre-launch security actions:

- Rotate all admin/demo credentials.
- Confirm production CORS/CSRF origins are exact, not wildcard-like.
- Confirm public estimate/campaign/issue links expire/revoke as intended.
- Run a manual role matrix test with real accounts.
- Keep private documents on signed/private storage, not public media storage.

## Frontend Findings

Validation passed:

- ESLint clean.
- Production build passed.
- Playwright smoke suite passed, 9 tests.

Hardening state:

- The recent React hook warning cleanup kept lint clean.
- Widget-level fallback behavior is present for operations page failures.
- Playwright covers dashboard customization and training access.

Recommended frontend additions:

- Add a Playwright workflow smoke covering import template download and import preview upload.
- Add a Playwright role matrix smoke for finance/operations/field/client sidebar visibility.
- Add slow-network UI smoke for Operations dashboard partial loading.

## Backend Findings

Validation passed:

- `manage.py check`
- `makemigrations --check --dry-run`
- `migrate --check` after applying local `observability.0012_operationalmode`
- 278 backend tests
- `pip check`

Hardening state:

- The local database had one unapplied maintenance-mode migration at the start of this pass. It was applied locally and is a production deployment prerequisite.
- Deployment check reports OpenAPI schema warnings and environment-dependent SSL/HSTS/secret warnings. These should be reviewed, but they are not current runtime blockers.

Recommended backend additions:

- Add CI step for `python manage.py migrate --check`.
- Add schema-generation cleanup for drf-spectacular warnings after launch stabilization.
- Add explicit serializers or schema annotations for APIViews that are intentionally response-dict based.

## Mobile Findings

Validation passed:

- `npm install`
- `npm run lint`
- `npx tsc --noEmit`
- `npx expo-doctor` with 17/17 checks passed

Hardening changes:

- Removed auth/profile console logging.

Remaining risk:

- `npm audit` reports 6 moderate findings in Expo/Metro transitive dependencies. The available fix is an Expo major SDK upgrade and should be scheduled as a separate mobile platform upgrade milestone.

## Predictive Safety Review

Current predictive layer remains safe for launch:

- Explainable scoring only.
- Human-in-the-loop recommendations.
- No automatic POE approval.
- No automatic financial changes.
- No campaign lifecycle mutations.
- No destructive operational automation.

Recommended follow-up:

- Add snapshot tests for representative predictive payloads and confidence ranges.
- Add UI copy review to ensure predictions never sound like final decisions.

## QA Conclusion

OMMS is ready for controlled production launch after environment setup and production migration execution. The remaining issues are operational deployment tasks and dependency governance, not blocking application defects.
