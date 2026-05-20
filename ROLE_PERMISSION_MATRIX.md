# OMMS Role Permission Matrix

## Platform Role

| Role | Scope | Purpose |
| --- | --- | --- |
| Platform Super Admin | OMMS platform tenant | Manage SaaS tenants, platform diagnostics, and future plans/subscriptions. |

Platform super admin access is based on Django superuser status plus membership in the `platform` tenant. Client company admins cannot grant platform-level permissions.

## Built-In Company Roles

| Role | Scope | Typical Access |
| --- | --- | --- |
| Company Admin | Own company tenant | Users, operations, company workflows, tenant-safe configuration. |
| Operations | Own company tenant | Campaign operations, inventory workflow, POE review, alerts, imports/exports where allowed. |
| Finance | Own company tenant | Billing, invoices, payments, collection analytics, finance alerts. |
| Field Staff | Own company tenant | Assigned work, POE upload, mobile field workflow. |
| Client | Own allowed client context | Client-visible campaign, POE, invoice/statement views where enabled. |

## Phase 1A Enforcement

Implemented now:

- company admins are tenant-scoped in user and directory APIs
- platform super admins can see users across tenants
- tenant identity is included in auth/current-user payloads
- company admins cannot assign users to another tenant

## Future Custom Role Engine

Phase 2 should add tenant-scoped custom roles and capabilities for:

- campaigns
- inventory
- POE
- billing
- imports/exports
- operations dashboard
- alerts/escalations
- training documents
- mobile access

Custom roles must never grant platform-level permissions and must keep finance, operations intelligence, exports, dashboards, and mobile APIs tenant-scoped.

## Phase 1B Role Implications

The audit found that role checks alone are not sufficient for SaaS isolation. Backoffice roles currently answer "what can this user do?" but not always "which tenant data can this user touch?"

Phase 1C must combine role permission checks with tenant ownership checks for:

- admin/operations inventory and campaign access
- finance billing and export access
- mobile admin operational summaries
- operations dashboard analytics
- operational search and saved views
- alerts, escalations, and notifications

Field staff should continue to see only assigned work. Client users should continue to see only client-safe campaign/POE/billing views, and those views must also remain tenant-derived.

## Phase 1C Enforcement Update

Inventory and campaign root APIs now combine role checks with tenant checks:

- platform super admins can inspect root inventory/campaign data across tenants
- company admins, operations, sales, finance, field staff, and clients are limited to their tenant for inventory/campaign roots
- clients still only see campaigns and inventory linked to their own campaign access
- company users cannot create campaigns with another tenant's client/account manager
- company users cannot create media units, rate cards, or inventory images against another tenant's site/unit

## Phase 1D Enforcement Update

Dependent operational workflows now inherit tenant boundaries from the Phase 1C roots:

- company admins and operators can access only bookings whose campaign belongs to their tenant
- booking creation validates that the campaign, media unit/site, and assigned user are in the same tenant
- POE review, media upload, verification, SLA analytics, and duplicate upload checks use `booking.campaign.tenant`
- issue visibility, issue creation, and issue task assignment use `booking.campaign.tenant`
- field staff mobile APIs remain assignment-only and now additionally require assigned bookings to belong to the user's tenant
- mobile admin operational summaries are tenant-scoped for company admins
- platform superadmins retain cross-tenant visibility for support and diagnostics

Finance and billing are partially tenant-filtered where they appear in operations/mobile summaries, but full billing API and invoice-number enforcement remain a Phase 1E responsibility.

## Phase 1E Enforcement Update

Finance, jobs, alerts, search, and dashboard preferences now combine role checks with explicit tenant filters:

- finance users can list and manage only invoices, payments, credit notes, statements, suppliers, and estimates tied to their tenant
- company admins can see tenant billing only where their role permissions allow it
- import/export jobs are owned by tenant and cannot be retried, confirmed, downloaded, or listed across tenants
- alert events, alert notifications, notification logs, saved views, and dashboard widget preferences are tenant-owned
- operational search and operations dashboard aggregations are tenant-scoped before result rendering
- platform superadmins retain global visibility for support and SaaS operations

Still deferred:

- company admins cannot create platform-level permissions
- tenant-scoped invoice/estimate sequences and custom tenant roles remain future work
- field staff and client users remain restricted from internal operations intelligence and finance analytics unless a specific client-safe surface already exists
