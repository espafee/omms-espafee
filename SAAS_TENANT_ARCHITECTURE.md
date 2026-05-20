# OMMS SaaS Tenant Architecture

## Phase 1A Scope

OMMS now has a safe tenant identity foundation for controlled multi-tenant evolution.

The first milestone intentionally focuses on users and platform administration. It does not rewrite campaign, billing, inventory, booking, POE, or invoice identifiers yet because those models currently use global uniqueness constraints that require a separate audited migration.

## Tenant Hierarchy

- OMMS Platform Owner / Super Admin
- Tenant / Client Company
- Company Admin
- Built-in company roles
- Future tenant-scoped custom roles

## Tenant Model

`apps.tenants.Tenant` stores:

- company name and slug
- tenant type: `platform` or `client`
- tenant status: `trial`, `active`, `suspended`, `cancelled`
- contact email
- default-client marker
- metadata for future SaaS plan and subscription fields

Seeded tenants:

- `omms-platform`: platform-owner tenant for OMMS super admins
- `vistaai-omms-beta`: default client tenant for current beta users and preserved single-company workflows

## User Tenant Link

`apps.users.User` now has a nullable protected foreign key to `Tenant`.

Migration behavior:

- existing Django superusers are assigned to `omms-platform`
- existing non-superusers are assigned to `vistaai-omms-beta`
- runtime user saves also assign a safe default tenant if one is missing

## Admin Distinction

Platform super admin:

- `is_superuser=True`
- tenant type is `platform`
- can see users across tenants in the Phase 1A user-management surface

Company admin:

- built-in role is `admin`
- tenant type is `client`
- can manage users only inside their own company tenant

## Current Tenant Scoping

Phase 1A tenant scoping is enforced for:

- user list/queryset access
- client directory
- field staff directory
- user tenant assignment validation
- token/current-user tenant claims
- Django admin tenant visibility fields

Existing operational modules continue to use their current beta-safe scoping while the business-data migration is planned.

## Next Safe Migration Steps

Phase 1B should add tenant keys to operational data in small groups:

1. inventory and media units
2. campaigns and bookings
3. POE records
4. billing and invoice sequences
5. imports/exports, notifications, search, dashboards

Each step should include data backfill, scoped uniqueness design, and tenant-isolation tests before production deployment.

## Phase 1B Audit Plan

Phase 1B keeps the database schema stable and documents tenant ownership before operational data is moved.

New audit artifacts:

- `TENANT_SCOPING_AUDIT.md`: model-by-model ownership, constraints, API surfaces, and sequencing.
- `TENANT_SCOPING_PLAN.json`: compact machine-readable transition plan.
- `apps.tenants.audit`: code-level audit constants used by tests to prevent accidental loss of migration scope.

Phase 1C should start with inventory and campaigns because they are the cleanest ownership roots for the rest of the platform. Billing, POE, issues, mobile admin, search, dashboards, imports/exports, and observability should then derive tenant filters from those roots.

Until Phase 1C is complete, do not onboard more than one real client tenant into shared production data.

## Phase 1C Inventory And Campaign Roots

Phase 1C adds tenant ownership to the clean operational roots:

- `inventory.MediaSite.tenant`
- `campaigns.Campaign.tenant`

Existing records are backfilled safely:

- sites without a tenant are assigned to `vistaai-omms-beta`
- campaigns without a tenant are assigned from `campaign.client.tenant`, falling back to `vistaai-omms-beta`

Inventory and campaign repositories now scope root and direct child querysets by tenant:

- platform super admins can access all tenant roots
- company users see only their own tenant roots
- client users keep the stricter client-owned campaign behavior

Global uniqueness remains unchanged for `MediaSite.code` and `Campaign.code`. Scoped uniqueness should be introduced only after duplicate-code audits are complete.
