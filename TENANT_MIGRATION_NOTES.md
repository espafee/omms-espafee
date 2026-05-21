# OMMS Tenant Migration Notes

## Current Safe Migration

The first SaaS migration adds a tenant model and links users to tenants while preserving existing single-company beta workflows.

Data backfill:

- superusers are assigned to `omms-platform`
- all other existing users are assigned to `vistaai-omms-beta`

This is safe because it does not rewrite operational business records or change existing operational identifiers.

## Destructive-Risk Area

The following models currently use global uniqueness or global sequencing and must not be converted casually:

- `MediaSite.code`
- `MediaUnit.unit_code`
- `Campaign.code`
- `Invoice.invoice_number`
- `InvoiceSequence.document_type + financial_year`
- `CampaignEstimate.estimate_number`
- POE `client_upload_id`
- billing GST/Supplier identifiers where legal uniqueness rules may differ from tenant uniqueness

Changing these constraints to tenant-scoped uniqueness requires:

- production data audit
- conflict detection
- scoped backfill
- revised indexes/constraints
- rollback/forward-fix plan
- role and API smoke tests per tenant

## Recommended Phase 1B Strategy

Proceed app by app:

1. Add nullable tenant FK.
2. Backfill from related user/client/campaign where deterministic.
3. Add read filters using tenant helper services.
4. Add write-time tenant assignment.
5. Add tests for two tenants with colliding natural codes where future scoped uniqueness is intended.
6. Only then replace global uniqueness constraints.

If conflicts are found, stop and resolve data ownership before altering constraints.

## Phase 1B Audit Findings

The Phase 1B audit identified the following ownership roots:

- Inventory ownership starts at `MediaSite`; units, rate cards, and images derive from the site.
- Campaign ownership starts at `Campaign`; assets, bookings, POEs, issues, invoices, and public campaign tokens derive from the campaign.
- Billing has two ownership roots: tenant-owned supplier/sequence configuration, and campaign-derived invoices/payments/credit notes.
- Observability records currently store `company_name`; Phase 1C should add a real tenant FK while retaining `company_name` as a display snapshot for historical readability.
- Mobile admin services currently aggregate global data and must be tenant-filtered before multi-tenant beta accounts are added.
- Setup profile and organization email settings are global singletons and require a later tenant-specific settings migration.

Detailed surfaces are documented in `TENANT_SCOPING_AUDIT.md`; a compact machine-readable plan is available in `TENANT_SCOPING_PLAN.json`.

## Phase 1C Safety Gate

Before adding tenant FKs to operational records, run a production data audit for duplicate natural identifiers:

- site codes
- unit codes
- campaign codes
- invoice numbers
- estimate numbers
- non-empty POE client upload IDs

If any duplicate exists across intended tenants, resolve ownership before enforcing scoped uniqueness.

## Phase 1C Completed Scope

Implemented:

- `MediaSite.tenant`
- `Campaign.tenant`
- reversible backfill migrations for both models
- tenant-scoped inventory repositories for sites, units, rate cards, site images, and unit images
- tenant-scoped campaign repositories for campaigns, campaign assets, and campaign access tokens
- write-time tenant assignment for new sites and campaigns
- same-tenant validation for campaign client/account manager and inventory unit/site relationships

Not yet changed:

- global unique constraints on `MediaSite.code` and `Campaign.code`
- bookings, POE, billing, import/export, search, dashboards, notifications, setup, and mobile admin aggregation

Phase 1D should derive bookings, POEs, issues, and mobile assigned-work/admin views from `Campaign.tenant`.

## Phase 1D Derived Tenant Scoping

Implemented without adding tenant fields to dependent operational records:

- bookings derive ownership from `booking.campaign.tenant`
- POE records and media derive ownership from `poe.booking.campaign.tenant`
- issues and issue tasks derive ownership from `issue.booking.campaign.tenant`
- mobile assigned work derives ownership from `booking.campaign.tenant` and still requires assignment for field staff
- mobile admin overview, running campaigns, POE tracker, daily activity, alerts, and issues are filtered through derived tenant paths
- POE analytics, POE SLA intelligence, operational heatmap POE/booking aggregates, operational search for campaigns/sites/units/POEs/invoices/clients, and export payload builders now accept the requesting user and apply derived tenant scoping where supported

Validation rules now enforced:

- company users cannot list or retrieve another tenant's bookings, POEs, or issues
- booking creation rejects cross-tenant campaign/media-unit combinations
- POE creation and verification reject cross-tenant bookings/records
- issue task assignment rejects assignees outside the issue tenant
- platform super admins retain global visibility

Still intentionally deferred:

- adding tenant FKs directly to `Booking`, `ProofOfExecution`, `Issue`, `ImportExportJob`, `AlertEvent`, or billing records
- changing booking numbers, POE upload IDs, invoice numbers, estimate numbers, or media-unit unique constraints
- tenant-specific alert-rule ownership and notification fanout rules
- billing sequence and invoice-number tenant uniqueness

Phase 1E should focus on billing/finance scoping and invoice sequence strategy only after duplicate invoice/estimate number audits are complete.

## Phase 1E Finance, Jobs, Alerts, Search, Dashboard Scoping

Implemented safely:

- Added nullable, backfilled tenant ownership to `SupplierProfile`, `ImportExportJob`, `Notification`, `EmailNotificationLog`, `AlertRule`, `AlertEvent`, `SavedOperationalView`, and `DashboardWidgetPreference`.
- Supplier profiles backfill to the default beta client tenant.
- Import/export jobs backfill from `created_by.tenant`, falling back to the default beta client tenant.
- Notifications backfill from recipient tenant or related campaign/booking/POE/issue tenant where available.
- Saved views and dashboard preferences backfill from their owning user tenant.
- Alert events backfill from their rule tenant where known; existing global alert rules remain platform/global defaults.

Runtime enforcement:

- Finance APIs filter invoices/payments/credit notes/events/statements through `campaign.tenant` and restrict client lookups to the requester tenant.
- Import/export preview, confirmation, retry, and processing require the actor to match the job tenant unless the actor is a platform superadmin.
- Export payload builders carry the requesting user so CSV output is tenant-filtered.
- Alert evaluation checks tenant-scoped metrics per tenant, stores tenant on alert events, and applies cooldowns per rule plus tenant.
- Notifications and notification logs are tenant-filtered for company users and globally visible only to platform superadmins.
- Saved views/dashboard preferences are user-owned and tenant-owned.
- Operations dashboard and operational search apply tenant filters before aggregation/result rendering.

Still deferred:

- Do not change `Invoice.invoice_number`, `CampaignEstimate.estimate_number`, or `InvoiceSequence` uniqueness until a production duplicate/sequence audit is complete.
- Do not change `SupplierProfile.gstin` uniqueness until legal/business ownership rules are approved.
- Do not change `AlertRule.metric` uniqueness until a platform-default plus tenant-override model is designed.
- Do not change saved-view/dashboard preference unique constraints until legacy `company_name` snapshots are migrated or retired.

## Phase 1E Stabilization Result

Full regression validation after Phase 1E found and fixed runtime compatibility gaps for legacy rows that may temporarily have `tenant = NULL`:

- supplier profiles created before tenant backfill
- import/export jobs created before `ImportExportJob.tenant`
- notification logs and inbox notifications created before notification tenant ownership
- alert events and cooldown visibility created before alert-event tenant ownership
- actorless audit events and request logs used as system timeline/health telemetry
- operations summary notification/request aggregations

The compatibility rule is intentionally narrow: tenant-null legacy records are visible only where they were historically global/system records or where `company_name` is blank/current company. Tenant-owned records remain isolated by tenant. Backend regression now passes with 309 app tests.

## Phase 1F Tenant Identifier And Sequence Audit

Phase 1F is complete as an audit/planning layer only. No uniqueness constraints, invoice/estimate numbering behavior, import behavior, export behavior, or POE upload-id behavior changed.

New audit tooling:

- `apps.tenants.identifier_audit.build_tenant_identifier_audit()`
- `python manage.py audit_tenant_identifiers`
- `python manage.py audit_tenant_identifiers --format json`

The audit reports:

- global uniqueness blockers for site codes, unit codes, campaign codes, invoice numbers, estimate numbers, POE client upload ids, supplier GSTINs, alert metrics, saved views, and dashboard widget preferences
- normalized duplicate-risk groups
- null-tenant legacy counts for direct and derived tenant ownership paths
- sequence ownership gaps for invoice sequences, estimate numbers, POE idempotency, and import/export file naming

Phase 1G should not change constraints until the command has been run against production and any duplicate/case-collision or null-tenant findings have been resolved.
