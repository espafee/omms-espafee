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

## POE SLA And Reviewer Workload Intelligence

OMMS now makes delayed POE review risk visible before it becomes a campaign delivery problem. Pending POE reviews and unresolved suspicious proofs receive warning and breach states based on clear operational SLA windows, and those signals appear directly in the POE queue and Operations dashboard.

The Operations dashboard now summarizes POE SLA warnings, breaches, oldest pending proof, unassigned review backlog, suspicious unresolved proofs, and reviewer workload distribution. This gives operations teams a compact way to balance review ownership and escalate risky campaigns without changing field upload behavior.

## Invoice Overdue Escalation And Collection Efficiency

OMMS now surfaces receivables risk before revenue delays become invisible backlog. Billing intelligence calculates overdue value, age buckets, collection efficiency, payment trends, average payment delay, and the clients carrying the largest overdue exposure.

The Operations dashboard adds a compact billing risk panel for admin and finance users, while Billing invoice rows now carry escalation labels and payment-risk hints. Overdue invoice alerts continue through the existing cooldown-protected alert system and now notify finance/admin inboxes for clearer ownership.

## Campaign Performance Analytics Foundation

OMMS now connects campaign delivery, POE completion, and commercial risk into one campaign performance layer. Campaigns receive a computed risk label without changing their lifecycle state, so owners can see which campaigns are on track, need attention, have POE risk, have billing risk, or are critical.

The Operations dashboard now includes campaign risk distribution, POE completion trend, operational health trend, critical campaign count, and a compact performance table, while the Campaigns page shows POE completion, pending proof counts, billing status, operational delay indicators, and risk badges per campaign. Mobile admin gets high-level campaign risk KPIs without exposing field staff to finance detail.

## Global Operational Search And Saved Views Foundation

OMMS now has the first layer of cross-operational navigation. Admin, operations, and finance users can search across campaign delivery, POE records, import/export jobs, alerts, audit history, notifications, and inventory records from the app shell without jumping through separate modules.

Saved operational views turn repeated filters into reusable work surfaces. Operators can save views such as `Critical Campaigns`, `Pending POEs`, `Failed Imports`, or `Today’s Operations`, then restore those filters on the Operations dashboard. Finance-sensitive search remains permission-protected, and mobile admin receives only a lightweight campaign/site lookup foundation.

## Role-Based Dashboard Customization Foundation

OMMS dashboards now start from the user's role instead of a one-size-fits-all layout. Admin/owners see operational health, critical campaigns, billing risk, alerts, campaign performance, and POE SLA first. Operations users see POE SLA, reviewer workload, campaign risk, jobs, and alerts. Finance users see overdue invoices, collection efficiency, payment trends, and billing alerts. Field staff and clients stay focused on their own execution or campaign visibility.

The first customization layer lets back-office users hide/show safe optional widgets and restore role defaults. This keeps dashboards personally useful while preserving the important guardrails: finance widgets do not leak to operations or field users, and operational intelligence does not leak to client or field dashboards.

## API Health Diagnostics And Environment Status

OMMS now gives admins a compact answer to a very operational question: is the platform healthy right now? Diagnostics combine API health, database connectivity, Redis/Celery configuration, failed or slow requests, failed background jobs, and last successful import/export activity into one safe system status payload.

The Operations dashboard now shows this as a System Status panel with calm health badges and non-secret deployment context. Degraded health can trigger the existing alert/notification path, while mobile admin receives only a tiny health summary suitable for an operations companion.

## Dashboard Customization Wiring Fix

Dashboard customization now changes the actual dashboard, not just the checklist. When a back-office user hides a safe optional widget, the matching dashboard card or section disappears immediately after save and remains hidden after refresh or a new login.

The dashboard also stops requesting billing summary data when all finance widgets are hidden, while still preserving role and permission guardrails. Restore defaults visibly rebuilds the role-default layout, and required widgets are clearly marked so users understand why they cannot be disabled.

## Dynamic Dashboard Widget Architecture

The dashboard has moved from grouped static panels to a true widget-rendering model. Each dashboard profile widget key now maps to a concrete widget component, and the page renders the saved active widgets in preference order.

This makes customization behave like users expect: selecting Campaign Performance shows that widget, hiding Billing Risk removes that widget, and future widgets can be added through the registry without reshaping the whole dashboard page. Unknown or unauthorized widgets are ignored safely.

## Maintenance Mode And Environment Control

OMMS now has a first controlled-environment layer for deployments, migrations, and incidents. Admins can place the platform into normal, degraded, maintenance, or read-only mode from Operations, with a clear global banner communicating the current state to users.

The implementation is conservative: safe reads and login stay available, admin diagnostics remain reachable, and non-admin write actions are blocked only in maintenance/read-only modes. Mobile follows the same source of truth, showing field users when changes are temporarily disabled and preventing POE submission while the backend is write-blocking.

## Inventory Import Template Download

The Operations import/export workbench now gives users the correct inventory onboarding format before they upload data. A `Download Excel Template` action generates `OMMS_Inventory_Import_Template.xlsx` from backend code, including required site columns, optional unit/GPS fields, sample rows, dropdowns, and instructions.

This makes the staged import workflow safer for onboarding teams: they can start with a verified workbook, understand that GPS coordinates are optional, and still rely on preview/confirmation before any inventory records are committed.

## Operations Dashboard Polish And Timeline Reliability

The Operations dashboard received a small but important reliability and polish pass. System Status now separates Celery and Worker readiness into readable cards, POE SLA rules are displayed as clear warning/breach rows, and compact cards wrap safely instead of colliding text.

The audit timeline now loads reliably again after fixing its serializer contract. If a future timeline refresh fails, the dashboard keeps the warning local to that widget instead of alarming the entire Operations page.

## Training Center Modernization

OMMS training materials have been refreshed to match the current product instead of the older static workflow manuals. The Training Center now serves regenerated enterprise PDFs with current web SaaS screenshots, mobile app visuals, operational terminology, role dashboards, alerts, imports/exports, POE review, billing intelligence, diagnostics, maintenance mode, and mobile field workflows.

The guide set now covers the Admin Guide, Operations Guide, Finance Guide, Field Staff Guide, Inventory Import Guide, POE Review Guide, Dashboard & Alerts Guide, Mobile App Quick Start Guide, and the Master Training Manual. The secure backend download architecture remains unchanged, so users still only see the guides appropriate for their role.

## Operational Activity Heatmap Foundation

OMMS now has the first layer of spatial and temporal operational intelligence without turning the dashboard into a technical analytics console. The Operations dashboard surfaces plain-language hotspot signals: busy areas, suspicious activity areas, delayed POE areas, campaign concentration, and reviewer load.

The design stays simple outside and powerful inside. Operators first see what needs attention, while deeper region, campaign, and reviewer details stay behind `View details`. The feature is analytics-only and does not change POE verification, GPS capture, campaign workflows, or field execution behavior.

## Predictive Operations Foundation

OMMS has taken the first safe step from operational intelligence toward predictive operational intelligence. The platform now scores campaign risk, forecasts reviewer pressure, detects rule-assisted suspicious patterns, highlights collection risk, and suggests interventions without executing anything automatically.

Every recommendation remains explainable. Operators can see why a campaign is high risk, why reviewer load may breach, or why a suspicious region needs attention. The UI keeps the simple question first: what should we do next?
