# Product Journey

## Operational SaaS Infrastructure Phase - Celery and Beat Wiring

OMMS now has production-oriented Celery configuration for background jobs while preserving current Django, DRF, frontend, observability, notification, POE, billing, and training workflows.

The implementation keeps scheduled work intentionally small. Celery Beat registers only jobs with clear existing support or minimal safe behavior: overdue invoice status maintenance and expired public campaign access token deactivation. Redis-compatible broker and result backend settings are driven entirely through environment variables, with local defaults suitable for development and Docker.

This keeps OMMS moving toward a reliable SaaS operating model without introducing speculative background behavior for notification retries, analytics refreshes, alert evaluation, exports, or imports before those flows have tenant-aware idempotency and dedicated tests.

## Verification Pass - Repository and Test Discovery Alignment

Before adding the next feature layer, OMMS was rechecked from the active repository at `/Users/macbook/Projects/OMMS`. The Celery/Beat wiring remained uncommitted but valid: Redis support is installed through the pinned backend requirements, Celery loads against the Django settings, and both safe scheduled tasks are registered.

The apparent test-count mismatch was traced to repository context rather than a failing discovery path. This active OMMS checkout currently discovers and passes 96 backend tests under `apps`; the earlier approximately-200-test signal aligns with a different TrustDial backend checkout, not this OMMS repository. Likewise, Playwright reports `No tests found` because this OMMS frontend has no committed Playwright config or spec files. Playwright specs were found only in another local repository, so no replacement smoke tests were added during this verification pass.

The result is a cleaner infrastructure baseline: Celery/Beat is ready to deploy once the uncommitted changes are reviewed and committed, while frontend smoke coverage remains a known follow-up that should be restored from the correct OMMS source rather than recreated blindly.

## Frontend Smoke Test Foundation

OMMS now has a minimal Playwright smoke suite for the active frontend checkout. The goal was not to redesign or expand product behavior, but to prevent the previous `No tests found` state from hiding frontend regressions.

The smoke suite verifies the login page, unauthenticated protected-route guards, the authenticated app shell/navigation, and stable billing, inventory, and campaign route loads. Because no real test credentials are available, authenticated checks use localStorage session seeding and mocked read-only API responses. This gives the project a repeatable browser-test baseline while keeping true live-login and backend-integrated smoke tests as a later, credential-backed step.

## POE Review Experience Polish

The POE review surface has been tightened for a more enterprise SaaS feel. Recent evidence cards now use consistent horizontal media rows on desktop, uniform thumbnail ratios, predictable metadata ordering, and stable verified badge placement. On smaller screens the same content stacks cleanly without changing API behavior.

The signed-in status message visible in the screenshot was traced to the TrustDial OMMS iframe wrapper rather than the OMMS frontend itself. It now behaves as a temporary session toast instead of a permanent floating banner, keeping the embedded dashboard clear after sign-in.

## Inventory Import Preview Foundation

OMMS now treats inventory import as a staged operational workflow rather than a direct upload action. The first safe phase is in place: teams can upload CSV or Excel inventory files, parse them, review validation results, inspect duplicates and warnings, and confirm that no records have been imported yet.

This preview foundation preserves onboarding speed while reducing operational risk. It checks missing required fields, repeated rows, duplicate site/media unit codes, invalid pricing or dimensions, and suspicious coordinates without committing inventory records. The Operations screen now gives users compact summary counts, row-level warnings/errors, duplicate information, preview rows, and a disabled `Start Import` placeholder for the next confirmation/background-processing phase.

## Inventory Import Confirmation Workflow

The staged import flow now continues past preview into explicit confirmation and background-safe processing. Operators must confirm a previewed job before any inventory records are created, and the system rejects stale, completed, running, or cross-company jobs.

Once confirmed, OMMS queues the import for Celery processing, tracks progress on the import job, imports only preview-ready rows, skips failed rows, avoids accidental overwrites, and reports imported, updated, skipped, and failed counts back to the Operations workbench. Completed imports now leave an audit trail and an operations notification titled `Inventory import completed`.

## Export System Expansion Phase 1

OMMS exports now use the same operational job backbone as imports. Inventory, campaign, POE, and invoice/payment exports can be started from the Operations workbench, queued for Celery processing, tracked with progress and duration, and downloaded after completion.

This keeps exports safer for larger operational datasets: jobs are company-scoped, permission-protected, auditable, and represented in the notification inbox when complete. CSV remains the first supported format; richer Excel formatting can come later without changing the job lifecycle.

## Operations Intelligence Dashboard Enhancements Phase 1

The Operations page has moved from a task bench into a first-pass operational intelligence dashboard. Admin and operations users now get compact KPIs, filtered charts, a unified activity timeline, and lightweight system health signals in the same place they manage imports and exports.

This phase focuses on visibility without risky data movement: analytics are aggregated server-side, scoped by company and role-aware filters where supported, and designed for quick operational decisions around jobs, request failures, POE review load, billing movement, notifications, and Celery-backed background activity.

## Notification Preferences UI

OMMS users can now tune operational notifications from the Notification Center. The preference panel groups alerts into practical SaaS categories such as imports, exports, POE review, billing, system diagnostics, and campaigns, with separate controls for inbox and email delivery.

The inbox remains intact for existing notifications, while future reads respect each user's muted in-app categories, including shared operations-role notifications. This gives teams more control over operational noise without weakening auditability or the notification infrastructure already used by imports, exports, billing, POE, and diagnostics.

## Alert Thresholds Phase 1

OMMS now has a first operational alert threshold layer for detecting risk without manual inspection. The system can evaluate failed imports/exports, suspicious POE spikes, overdue invoices, failed API requests, and slow API requests, then create an audit trail plus an operations inbox notification when a rule breaches.

The Operations dashboard now shows alert thresholds alongside current values and last trigger times. Admins can tune thresholds or pause a rule, while cooldown handling prevents repeated notifications from becoming operational noise.

## Operational Alert Acknowledgement

The alert system now supports the next operational behavior: acknowledgement. Teams can mark a live alert as acknowledged directly from the Operations dashboard, preserving the alert history while making it clear that someone has seen and accepted ownership of the risk.

Cooldown visibility is now part of the alert threshold experience as well. Instead of silently suppressing duplicate alerts, OMMS shows the remaining cooldown window so operations users understand why an alert has not repeated yet. This keeps alerting useful without turning the dashboard into noise.

## Operational Auto-Refresh And Live Activity

The Operations dashboard now behaves more like an active command surface. It quietly refreshes core operational signals in the background, keeps alert and timeline state current, and updates import/export progress without requiring manual reloads.

The live layer is intentionally calm: a compact `Live` indicator, last-updated text, and subtle activity pulse communicate freshness without turning OMMS into a noisy wallboard. Browser tabs pause refresh when hidden, and running jobs use a focused refresh cadence so operators can watch progress while the system avoids unnecessary request load.

## Failed Import/Export Retry Workflow

OMMS can now recover from failed operational jobs without losing history. Failed imports and exports expose a controlled retry action in the Operations workbench, creating a linked retry job while preserving the original failure record and report.

Inventory retries remain safe by reusing the import preview metadata and idempotent import rules, so retrying a failed import does not blindly duplicate sites or media units. Export retries regenerate the requested CSV from the original filters. Each retry request is audited, and completion or failure continues to flow through the notification system.
