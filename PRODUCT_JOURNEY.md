# Product Journey

## Location And Advertising Unit Inventory Workspace

Inventory now makes the commercial hierarchy explicit: **Location → Advertising Unit → Bookings / Campaigns / POE**. The default `/inventory?view=units` list is the operational sales surface; Locations remain a separate physical-place list at `/inventory?view=locations`, and `/inventory?view=overview` is intentionally compact. This is a terminology and interaction improvement only: the existing `MediaSite` and `MediaUnit` APIs, records, tenant scoping, booking links, POE links, campaign previews, public campaign image URLs, and permissions remain unchanged.

Lists are the default so teams can compare availability, direction, rate, dimensions, parent location, and photo completeness without opening a gallery for every record. Photos are managed on demand in a focused drawer using the existing public image endpoints; private document URLs are never used. Admin-only Location creation/deletion and operations/admin Unit/photo rights remain backed by the existing server-side permissions.

## All Sites Inventory List

Inventory now has a complete All Sites list view backed by `GET /api/v1/inventory/sites/all-sites/`. The endpoint uses `MediaSite` as the source of truth so newly created sites appear even before sellable media units are added, while related `MediaUnit` data supplies unit codes, dimensions, facing direction, single/both-side type, and availability where present.

The Inventory page now shows the list as a paginated table with search plus city, status, media type, facing direction, and site type filters. Rows use the same public inventory image behavior as existing site/unit galleries and link back into the existing gallery and media-unit edit flows, preserving the current create/edit/detail/gallery/public campaign workflows.

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

## Frontend Stability Warning Cleanup

OMMS received a quiet production-readiness pass on core operational pages. The recurring frontend hook warnings on Bookings, Campaigns, Inventory, POE Review, and Field POE Capture are now resolved with stable data-loading callbacks.

This does not change any user workflow. It makes the validation baseline cleaner, reduces surprise rerenders, and helps future product warnings stand out immediately instead of being hidden in known noise.

## Production Readiness And QA Hardening

OMMS moved from feature expansion into launch hardening. The platform now has a formal production readiness report, QA hardening report, and deployment checklist covering workflows, resilience, role safety, deployment configuration, mobile readiness, predictive safety, and operational risks.

The pass confirmed the application is ready for controlled production launch once environment setup is completed. The main remaining work is deployment discipline: production migrations, durable storage, Redis/Celery verification, domain/security configuration, and a planned mobile dependency upgrade review.

## Production Smoke Verification

The production smoke pass verified that the Render backend is alive and that `https://omms.vercel.app` is deployed with the correct backend API root. Protected operational endpoints correctly reject anonymous requests, which confirms the public surface is not accidentally exposing training, import/export, or maintenance controls.

The VistaAi launch-path issue has been resolved by redirecting `/omms/login` into the canonical OMMS beta app instead of embedding it in the marketing site.

## Controlled Beta Stabilization

OMMS has entered controlled beta stabilization. The recommended beta entrypoint is currently `https://omms.vercel.app` because it is deployed with the correct Render backend API root.

The product direction for this phase is deliberate: stabilize production, observe real workflows, keep the UI simple for operators, and avoid expanding predictive features until the deployment surface, worker health, storage, and role-based smoke checks are proven in production.

## VistaAi OMMS Launch Path Stabilized

The VistaAi marketing site now hands users into the canonical OMMS beta app instead of trying to embed it as a separate iframe experience. `/omms/login` shows a simple “Opening OMMS secure portal…” launch state and redirects to `https://omms.vercel.app/login`.

This keeps the beta launch clear and reliable: OMMS runs from the Vercel app already wired to the Render backend API, while VistaAi remains the marketing and discovery surface.

Production verification confirmed the live VistaAi page now redirects to `https://omms.vercel.app/login` and no longer embeds OMMS in an iframe.

## Render Backend Readiness Smoke

The Render backend is publicly healthy and serving the current operational API surface. Health, OpenAPI schema, and Swagger UI load successfully, while protected Training, import/export, and operational-mode endpoints correctly return `401` to anonymous users instead of leaking data or failing with server errors.

The remaining backend beta blockers are infrastructure proofs rather than code defects: confirm production migrations in Render, verify Redis/Celery worker and beat services, and run one authenticated safe background job from the production dashboard.

## Authenticated Beta Smoke Plan

OMMS now has a documented, repeatable production role-smoke plan for admin, operations, finance, field staff, and client users. The plan prioritizes non-destructive checks: login, role-appropriate navigation, dashboard customization, Training downloads, import-template download, notification inbox, operational search scoping, and mobile assigned-work/POE screens.

Execution is pending production credentials. The plan explicitly avoids changing maintenance mode, committing imports, or starting background exports until approved test data and worker verification are available.

## SaaS Tenant Foundation

OMMS has taken the first safe step from single-company beta platform toward multi-tenant SaaS. The platform now understands platform-owner tenants and client-company tenants, with existing beta users preserved inside a default VistaAi OMMS tenant.

This milestone keeps the product stable while establishing the SaaS spine: platform super admins are separate from company admins, company user directories are tenant-scoped, and auth payloads now carry tenant identity. The larger operational-data tenant migration is documented separately because inventory, campaign, invoice, and POE identifiers currently have global uniqueness rules that need an audited migration rather than a risky rewrite.

## SaaS Tenant Ownership Audit

OMMS now has a detailed tenant ownership audit for the operational platform. The audit maps inventory, campaigns, bookings, POEs, billing, issues, observability, notifications, training, and mobile surfaces into a safe Phase 1C migration sequence.

The key product decision is clear: OMMS should not onboard multiple real companies into shared production data until inventory and campaign ownership are tenant-scoped first. This keeps the SaaS evolution disciplined, protects beta trust, and avoids risky identifier rewrites.

## SaaS Inventory And Campaign Roots

OMMS now has tenant ownership on the first two operational roots: inventory sites and campaigns. This is the first real data-isolation step beyond user tenant identity.

For existing beta users, nothing visually changes. Sites and campaigns are safely assigned to the default beta tenant, while new company-created records attach to that user's company. Platform owners can still inspect across companies, but company users no longer see another tenant's inventory or campaign roots.

## SaaS Derived Operational Scoping

OMMS has extended tenant safety into the operational workflows that sit under campaigns and sites. Bookings, POE review, issue management, mobile assigned work, mobile admin summaries, POE analytics, operational search, and export payloads now derive company ownership from the tenant-scoped campaign/site roots.

This is intentionally invisible to normal beta users. The product keeps its current workflows, but the platform is safer for future multi-company operation: company teams stay inside their own bookings, proofs, issues, and mobile work queues, while platform owners keep cross-tenant oversight.

The next SaaS milestone should be finance-specific. Invoice and estimate numbering, billing sequence ownership, and tenant-aware alert/job ownership remain separate because they require careful production data audits before uniqueness rules change.

## SaaS Finance And Operations Isolation

OMMS has now closed the highest-risk remaining tenant visibility gaps around finance, operational jobs, alerts, notifications, search, and dashboard analytics.

For company users, billing data, import/export jobs, notification inboxes, alert events, saved views, dashboard preferences, operational search results, and operations dashboard counts now stay inside their own company tenant. Platform owners keep intentional cross-tenant visibility for support and SaaS operations.

This milestone deliberately avoids changing invoice numbers, estimate numbers, supplier GST uniqueness, and alert metric uniqueness. Those identifiers still need a production duplicate/sequence audit before OMMS moves from visibility isolation to fully tenant-scoped numbering.

The Phase 1E stabilization pass completed the full regression gate after the initial commit. Backend, frontend, Playwright, and mobile checks now pass, and compatibility was tightened for legacy records that may still have null tenant values during the transition.

## SaaS Tenant Identifier And Sequence Audit

OMMS now has a safe audit foundation for the next hard part of SaaS tenancy: natural identifiers and numbering. The platform can report which codes and sequences are still globally constrained, where null-tenant legacy records may exist, and which invoice/estimate/POE numbering paths need tenant ownership before constraints change.

This phase deliberately avoids changing production behavior. Site codes, unit codes, campaign codes, invoice numbers, estimate numbers, POE upload ids, alert metrics, saved views, and dashboard preferences continue working exactly as before. The value is launch safety: Phase 1G can now be planned from audit evidence rather than guesswork.

The local readiness pass has been captured, and OMMS now has a production runbook plus a Phase 1G go/no-go checklist. The next constraint migration is blocked until the same audit is run against production data and reviewed by platform, finance, operations, and deployment owners.

Production audit execution remains pending because authenticated Render shell/job access was not available from the current Codex environment. This keeps Phase 1G correctly in a no-go state until live data is reviewed.

## Executive Dashboard Experience

OMMS now gives owners and administrators a clearer first answer to the question that matters most: what is healthy, what is moving, and what needs attention now. The dashboard begins with a calm executive command center covering campaign health, live booking execution, POE coverage, collection performance, and priority risks.

The upgrade uses the platform's existing tenant-scoped summaries and role permissions, so the stronger international presentation does not weaken data isolation or create a second analytics contract. User-selected modules remain dynamic and persistent, while dashboard customization has moved into a compact secondary control. The result is a more credible leadership view without making the day-to-day product harder to understand.

## Campaign Operations Consolidation

Campaign operations now tell one consistent lifecycle story. OMMS distinguishes the administrative state chosen by the team from the effective state determined by tenant-local campaign dates, so an expired campaign can no longer appear active in the roster while its client link says it has ended.

The campaign workspace has also moved from fragmented roster, detail, and sharing blocks into one compact operational table. Teams can scan delivery, POE progress, budget, assets, billing, objective, and share-link state in one place, then open a dedicated internal detail route regardless of whether public sharing remains available. Copying a client link is now a quiet local action with clear confirmation and no page jump.

## Company Team And Access

OMMS company administrators can now manage access without leaving the operational product. The new Team & access workspace makes roles understandable in business language, keeps each company isolated, supports region and reporting-manager context, and uses a secure account-setup link instead of temporary shared passwords.

Removing access now means deactivation, not deletion. Campaign ownership, reviews, approvals, alerts, and audit history remain intact, while the former user can no longer authenticate. The same role definitions govern backend authorization, dashboard modules, and navigation so a hidden menu never substitutes for real permission enforcement.

## Live Media Planning And Formal Proposal Intake

Clients can now explore a controlled, date-aware media selection prepared specifically for them instead of receiving an unrestricted inventory spreadsheet. They see client-safe photos and facts, build a campaign shortlist on mobile or desktop, and submit it for formal availability and pricing review without reserving media.

Sales, operations, and finance receive the request in a shared pipeline. OMMS preserves what the client saw, rechecks availability, reuses the existing estimate approval journey, and converts only after authorized approval. The experience is polished while operational control remains inside OMMS.

## Planner Publishing And Filter Clarity

The Live Media Planner now makes its safety model clearer for both internal teams and clients. Internal users get direct confirmation when a secure link is generated, a visible warning if the link has no eligible published units, and a clear copy confirmation for the one-time URL.

Inventory publication remains opt-in. Existing units are not exposed automatically; authorized operators publish or unpublish advertising units from the inventory workspace when they are ready for client planning. On the public planner, filter controls now use tenant-safe options and empty states explain whether the owner has not published units, filters are too narrow, or selected dates exclude availability.

## Live Planner Visibility Reliability

The planner now handles older allowed-city configurations as safely as newly generated links. A link that stores `Jammu`, `jammu`, ` Jammu `, or comma-separated city values still finds the same tenant-owned published Jammu inventory. This keeps existing client links live when operators publish units after creating the link.

Internal teams also have a lightweight eligible-inventory preview, so a zero-unit link can be explained by a practical reason such as unpublished units, city restrictions, inactive units, or date availability rather than guesswork.

## Production Diagnostics Discipline

OMMS now has a controlled way to collect production evidence for Live Media Planner visibility issues without Render Shell access. A disabled-by-default platform diagnostics route lets a platform superadmin inspect safe pipeline counts, migration checks, build identity, and a non-reversible database fingerprint while avoiding raw tokens, secrets, contact data, and financial internals.

This keeps beta stabilization practical: when a production-only planner link shows zero units, the team can identify the exact exclusion stage, prove whether publishing and public reads use the same database, and disable the tool again after diagnosis.

The diagnostic evidence is now also available inside the existing Media Proposals workspace for platform admins. Each recent planner link can show eligible, published, and excluded unit counts, with a safe report for the ESPA units currently under investigation. Public clients only receive simple empty-state metadata, never internal exclusion details.
