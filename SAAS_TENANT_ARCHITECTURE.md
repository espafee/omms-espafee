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
