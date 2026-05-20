# OMMS Tenant Scoping Audit

Phase 1B was an ownership audit and transition plan only. Phase 1C has now added tenant ownership to the two clean root models: `MediaSite` and `Campaign`.

## Summary

Current OMMS beta behavior remains single-company by default, but inventory and campaign roots now carry tenant ownership. Client-facing access is still scoped by `campaign.client == request.user`; admin, operations, finance, mobile admin, observability, import/export, search, and dashboard surfaces outside inventory/campaign roots still need Phase 1D filtering.

Phase 1C should introduce tenant ownership in small audited groups, with data backfill and tenant-specific tests before any global uniqueness constraint is replaced.

## Model Ownership Findings

| Area | Models | Required Tenant Owner |
| --- | --- | --- |
| Inventory | `MediaSite`, `MediaUnit`, `RateCard`, `MediaSiteImage`, `MediaUnitImage` | `MediaSite.tenant` implemented; children derive by unit/site |
| Campaigns | `Campaign`, `CampaignAsset`, `CampaignAccessToken` | `Campaign.tenant` implemented; children derive by campaign |
| Bookings | `Booking`, `Assignment` | derived from `Booking.campaign.tenant` |
| POE | `ProofOfExecution`, `ProofOfExecutionMedia`, `ProofOfExecutionVerificationLog` | derived from `booking.campaign.tenant` |
| Billing | `SupplierProfile`, `InvoiceSequence`, `Invoice`, `InvoiceLine`, `Payment`, `CreditNote`, `InvoiceEvent`, `CampaignEstimate`, `CampaignEstimateLine` | `tenant` for supplier/sequence/estimate; invoice derived from campaign |
| Issues | `Issue`, `IssueEvent`, `IssueReportToken`, `IssueTask` | derived from booking/campaign tenant |
| Notifications | `Notification`, `EmailNotificationLog`, `NotificationPreference` | tenant for notifications/logs; preference stays user-owned and tenant-derived |
| Observability | `ApiRequestLog`, `AuditEvent`, `ImportExportJob`, `SavedOperationalView`, `DashboardWidgetPreference`, `AlertRule`, `AlertEvent` | tenant FK with `company_name` retained as display snapshot |
| Setup | `CompanyProfile`, `OrganizationEmailSettings` | should become tenant-specific singleton |
| Training | document visibility | role + tenant/plan gates in later plan phase |
| Mobile | assigned work, admin overview/search/alerts/issues | tenant-scoped through bookings/campaigns and user tenant |

## Global Constraints Requiring Redesign

- `MediaSite.code`: global unique to tenant + code
- `MediaUnit.unit_code`: global unique to tenant + unit_code
- `Campaign.code`: global unique to tenant + code
- `Invoice.invoice_number`: global unique to tenant + invoice_number
- `InvoiceSequence.document_type + financial_year`: global to tenant + document_type + financial_year
- `CampaignEstimate.estimate_number`: global unique to tenant + estimate_number
- `ProofOfExecution.client_upload_id`: global non-empty unique to tenant + client_upload_id where non-empty
- `SupplierProfile.gstin`: requires business decision; legal GST identity may be global, but supplier profile ownership should be tenant-scoped
- `AlertRule.metric`: global unique should become platform default plus tenant override model or tenant + metric
- `SavedOperationalView.user + company_name + name`: should become user + tenant + name
- `DashboardWidgetPreference.user + company_name + widget_key`: should become user + tenant + widget_key

## API And Queryset Surfaces Needing Scoping

Inventory:

- repositories now tenant-scope sites, units, rate cards, and inventory images
- import preview still detects duplicates globally with `MediaSite.code` and `MediaUnit.unit_code`
- import confirmation creates/fetches sites and units globally
- inventory export exports global inventory

Campaigns and bookings:

- campaign and campaign-asset repositories now tenant-scope backoffice users
- campaign serializer now tenant-scopes client/account-manager choices
- `BookingSerializer` primary-key fields still need tenant-scoped querysets in Phase 1D
- campaign public tokens remain globally resolvable by token, but responses must remain limited to the token's campaign only

POE:

- review queues and media APIs are global for backoffice roles
- `ProofOfExecutionVerifyRequestSerializer` uses `ProofOfExecution.objects.all()`
- mobile POE submission permission depends on assignment, but admin-like users can access all bookings until tenant scoping is added

Billing:

- finance/admin APIs are global today
- client statement resolution fetches `User.objects.get(pk=client_id)` without tenant filtering
- invoice/estimate serializers use global campaign/supplier/media-unit querysets in several places
- billing analytics must filter by tenant before aggregation

Observability and operations:

- operations summary uses global campaign, invoice, payment, POE, alert, request-log, and user aggregates in several sections
- search builders query campaigns, invoices, POEs, and inventory globally
- import/export jobs are scoped by `company_name`, which is display-oriented and not strong tenancy
- saved views/dashboard preferences still rely on `company_name`

Notifications:

- team notifications match by role and recipient but not tenant
- notification logs are global and need tenant metadata before cross-tenant operations

Issues and mobile:

- issue admin views and mobile admin issue/alert views are global for admin-like users
- mobile admin overview currently aggregates global campaigns, bookings, POEs, billing, heatmap, and predictive payloads

Setup and training:

- `CompanyProfile` and email settings are global singletons; Phase 1C/1D must convert them to tenant-specific settings
- training docs are role-gated only; future plan/training access gates should be tenant/plan-aware

## Phase 1C Sequencing Recommendation

1. Booking + POE + issue scoping next, because they can derive from campaign ownership.
2. Billing after that, now that campaign ownership exists and invoice sequence behavior can be decided.
3. Observability/import/export/search/dashboard fourth, adding real tenant FK while preserving historical `company_name` display.
4. Setup/training/plan gates fifth, when tenant-specific company profile and plan foundation are ready.

Each step should add two-tenant tests proving that admins, operations, finance, mobile admin, exports, search, and dashboards cannot see the other tenant.
