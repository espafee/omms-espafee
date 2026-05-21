# Phase 1G Identifier Constraint Checklist

Use this checklist before changing any tenant-scoped uniqueness constraint or sequence behavior.

## Universal Go/No-Go

| Item | Status |
| --- | --- |
| Production `audit_tenant_identifiers --format json` captured | Blocked - Render shell/access required |
| Production duplicate groups reviewed | Blocked - production audit not captured |
| Production null-tenant counts reviewed | Blocked - production audit not captured |
| Existing issued invoice numbers will remain unchanged | Required |
| Existing estimate numbers will remain unchanged | Required |
| Existing POE `client_upload_id` behavior preserved until DB constraint migration | Required |
| Rollback/forward-fix plan written for the specific migration | Pending |
| Migration limited to one identifier family | Required |
| Full backend regression planned after migration | Required |
| Frontend/mobile smoke planned if affected | Required |

## Inventory Site Code

Go only if:

- `MediaSite.code` duplicate groups are `0`
- `MediaSite.tenant` null count is `0`
- imports reject cross-tenant conflicts until the DB constraint changes

No-go if:

- same normalized site code appears in multiple tenants
- any site lacks tenant ownership

## Media Unit Code

Go only if:

- `MediaUnit.unit_code` duplicate groups are `0`
- every unit has a site with tenant ownership
- Phase 1G decides whether to add direct `MediaUnit.tenant`

No-go if:

- tenant ownership cannot be enforced at the DB level
- same normalized unit code appears across tenants and must be preserved

## Campaign Code

Go only if:

- `Campaign.code` duplicate groups are `0`
- `Campaign.tenant` null count is `0`
- campaign public-token behavior remains unchanged

No-go if:

- campaign code collisions exist
- public links or exports depend on global campaign-code uniqueness without fallback

## Invoice Number And Sequence

Go only if:

- `InvoiceSequence` tenant ownership migration is designed first
- allocation accepts tenant context
- existing invoice numbers remain immutable
- legal/business decision allows tenant-scoped invoice numbers

No-go if:

- production has invoices with missing campaign tenant
- sequence ownership is still global
- support/legal wants invoice numbers globally unique across the SaaS

## Estimate Number

Go only if:

- estimate tenant ownership is explicit or safely derived
- a tenant-owned estimate sequence is designed
- old estimate numbers remain immutable

No-go if:

- estimates have missing client/campaign tenant paths
- current global primary-key based number is still the only generator

## POE Client Upload ID

Go only if:

- POE tenant ownership is explicit or safely derived for every row
- non-empty `client_upload_id` duplicate groups are `0`
- mobile retry/idempotency tests are included

No-go if:

- any non-empty upload id lacks a booking/campaign tenant
- cross-tenant id collisions must be preserved before the new constraint exists

## Alert Rule Metric

Go only if:

- platform default versus tenant override semantics are designed
- cooldown behavior remains tenant-aware
- global default rules are distinguishable from tenant rules

No-go if:

- `AlertRule.metric` is changed without a default/override strategy

## Saved Views And Dashboard Preferences

Go only if:

- all saved views/preferences have tenant ownership
- `company_name` is display-only and no longer needed for uniqueness
- restore-default and save/read tests are updated

No-go if:

- legacy rows still rely on `company_name` as the only company boundary

## Import/Export File Naming

Go only if:

- download authorization continues through `ImportExportJob.tenant`
- new storage paths include tenant/job context
- existing file paths remain downloadable

No-go if:

- path migration would break historical downloads

## Final Approval Before Phase 1G

Required reviewers:

- platform/backend owner
- finance workflow owner for invoice/estimate numbering
- operations owner for inventory/campaign/POE identifiers
- deployment owner for rollback timing

Final decision:

- `GO`: all targeted checks pass and migration is narrowly scoped
- `NO-GO`: any duplicate/null-tenant/sequence ownership issue remains unresolved

Current decision as of 2026-05-21:

- `NO-GO`: production audit has not yet been executed because authenticated Render shell/job access is unavailable in the current Codex environment.
