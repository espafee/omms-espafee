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
