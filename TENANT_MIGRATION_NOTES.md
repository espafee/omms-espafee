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
