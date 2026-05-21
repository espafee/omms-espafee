# OMMS Tenant Identifier Audit

Phase 1F is a read-only audit and planning milestone. It does not change database uniqueness constraints, numbering behavior, import behavior, export behavior, or beta workflows.

## Audit Command

Run:

```bash
python manage.py audit_tenant_identifiers
python manage.py audit_tenant_identifiers --format json
```

The command reports:

- global uniqueness blockers
- normalized duplicate-risk groups
- null-tenant legacy records
- sequence ownership gaps
- Phase 1G migration recommendations

The command is safe for production because it performs read-only counts and grouped queries.

## Related Readiness Artifacts

- `TENANT_IDENTIFIER_AUDIT_LOCAL_RESULT.md`: local audit output captured on 2026-05-21.
- `TENANT_IDENTIFIER_PRODUCTION_RUNBOOK.md`: exact production/Render runbook for capturing audit output safely.
- `PHASE_1G_IDENTIFIER_CONSTRAINT_CHECKLIST.md`: go/no-go checklist before any uniqueness or sequence migration.

## Identifier Targets

| Identifier | Current constraint | Tenant target | Phase 1G risk |
| --- | --- | --- | --- |
| `MediaSite.code` | Global `unique=True` | `tenant + normalized code` | Existing imports/search assume one global site code. |
| `MediaUnit.unit_code` | Global `unique=True` | `tenant + normalized unit_code` | Unit tenant is currently derived through `site.tenant`; a direct tenant FK or equivalent DB-supported design is needed. |
| `Campaign.code` | Global `unique=True` | `tenant + normalized code` | Campaign references, public campaign labels, search, and exports use this code. |
| `Invoice.invoice_number` | Global nullable `unique=True` | tenant-scoped issued invoice number | Requires tenant-owned invoice sequence first. |
| `CampaignEstimate.estimate_number` | Global nullable `unique=True` | tenant-scoped estimate number | Current number uses global DB id shape. |
| `ProofOfExecution.client_upload_id` | Global non-empty unique constraint | tenant-scoped non-empty upload id | Service retry lookup is tenant-aware, but DB still blocks duplicate mobile upload ids across tenants. |
| `SupplierProfile.gstin` | Global `unique=True` | pending business/legal decision | GSTIN may need to remain globally unique or become tenant-scoped by supplier profile ownership. |
| `AlertRule.metric` | Global `unique=True` | platform default plus tenant override | Needs a default/override model so tenant rules do not collide. |
| `SavedOperationalView.name` | `user + company_name + name` | `user + tenant + name` | Legacy `company_name` snapshot should be retired from uniqueness. |
| `DashboardWidgetPreference.widget_key` | `user + company_name + widget_key` | `user + tenant + widget_key` | Same legacy snapshot issue as saved views. |

## Duplicate-Risk Meaning

Current global unique constraints may prevent actual cross-tenant duplicates from existing today. The audit still checks normalized identifier groups so case-collisions such as `SITE-001` and `site-001` are visible before a tenant-scoped migration.

Before Phase 1G, production should show:

- no duplicate groups for identifiers being migrated
- no unresolved null tenant records for owned operational data
- no cross-tenant identifier conflicts hidden by legacy data

## Global Uniqueness Blockers

The following blockers must remain unchanged until Phase 1G migration scripts are reviewed:

- `inventory.MediaSite.code`
- `inventory.MediaUnit.unit_code`
- `campaigns.Campaign.code`
- `billing.Invoice.invoice_number`
- `billing.CampaignEstimate.estimate_number`
- `poe.ProofOfExecution.client_upload_id`
- `billing.SupplierProfile.gstin`
- `observability.AlertRule.metric`
- `observability.SavedOperationalView.user + company_name + name`
- `observability.DashboardWidgetPreference.user + company_name + widget_key`

Security tokens should stay globally unique and are not tenant natural identifiers:

- campaign access tokens
- estimate approval tokens
- issue report tokens

## Null-Tenant Checks

The audit checks direct and derived tenant ownership for:

- sites and campaigns
- supplier profiles
- invoices and estimates
- POEs
- import/export jobs
- notifications and notification logs
- notification preferences
- alert rules and events
- saved operational views
- dashboard widget preferences

Null tenant counts are not always launch blockers for historical system/global rows, but they are blockers before changing uniqueness constraints on business identifiers.

## Phase 1G Entry Criteria

Do not start constraint migrations until:

- `audit_tenant_identifiers --format json` has been captured from production
- null tenant ownership gaps are understood or fixed
- duplicate/case-collision groups are resolved
- invoice and estimate sequence ownership is designed
- rollback notes exist for each constraint migration

Local audit output is not enough for Phase 1G approval. Production output must be captured from the live database because local development may have no operational records.
