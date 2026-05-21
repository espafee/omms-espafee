# OMMS Tenant Sequence Strategy

Phase 1F identifies sequence and numbering risks only. It does not change production numbering.

Before Phase 1G, attach production output from `python manage.py audit_tenant_identifiers --format json` to the deployment notes and complete `PHASE_1G_IDENTIFIER_CONSTRAINT_CHECKLIST.md`.

## Principles

- Existing issued invoice and estimate numbers are immutable historical business identifiers.
- Tenant-scoped numbering must be introduced forward-only.
- Sequence changes must not alter PDFs, payment references, audit history, exports, or customer-visible links for old records.
- Security tokens remain globally unique.
- Human-entered/imported codes should become tenant-scoped only after duplicate audits pass.

## Inventory Codes

### `MediaSite.code`

Current: globally unique.

Target: unique within tenant.

Recommended migration:

1. Run `audit_tenant_identifiers`.
2. Resolve case-collisions and null tenant records.
3. Add application-level validation for `tenant + code`.
4. Replace global unique constraint with tenant-scoped uniqueness in a dedicated migration.

### `MediaUnit.unit_code`

Current: globally unique and tenant is derived through `site.tenant`.

Target: unique within tenant.

Recommended migration:

1. Decide whether to add `MediaUnit.tenant` directly or retain derived tenant ownership.
2. Prefer direct nullable `tenant` if the database must enforce `tenant + unit_code`.
3. Backfill from `site.tenant`.
4. Validate imports against tenant-scoped duplicates.
5. Replace global uniqueness only after backfill and duplicate audit pass.

## Campaign Codes

Current: `Campaign.code` is globally unique.

Target: unique within tenant.

Recommended migration:

1. Keep current code behavior during beta.
2. Audit duplicate/case-collision risks.
3. Add tenant-scoped validation.
4. Change DB uniqueness in a focused migration.

Public campaign access tokens remain globally unique and are not part of this scoped code migration.

## Invoice Numbering

Current:

- `InvoiceSequence` is keyed globally by `document_type + financial_year`.
- `allocate_invoice_number(document_type, financial_year)` increments that global sequence.
- `Invoice.invoice_number` is globally unique.

Target:

- `InvoiceSequence.tenant + document_type + financial_year`
- `Invoice.tenant + invoice_number` or derived tenant-scoped invoice-number uniqueness

Recommended migration:

1. Add nullable tenant ownership to `InvoiceSequence`.
2. Backfill existing sequence rows to the default beta tenant or create tenant-specific starting rows.
3. Update allocation to accept tenant.
4. Preserve already issued invoice numbers exactly.
5. Only then replace invoice-number uniqueness if the business accepts duplicate invoice numbers across tenants.

Open business decision:

- Some operators may prefer invoice numbers globally unique across the SaaS for support and legal clarity. If so, keep `Invoice.invoice_number` global but make the sequence tenant-aware for future prefixes.

## Estimate Numbering

Current:

- `CampaignEstimate.estimate_number` is generated as `EST/{created_at:%Y-%y}/{id:04d}`.
- The number uses global database id shape and is globally unique.

Target:

- tenant-owned estimate sequence or tenant-aware display number

Recommended migration:

1. Add explicit tenant ownership to estimates or derive safely from campaign/client.
2. Introduce a tenant-owned estimate sequence model.
3. Generate future estimate numbers from tenant context.
4. Preserve old estimate numbers.
5. Move uniqueness after production duplicate audit.

## POE Upload Idempotency

Current:

- `ProofOfExecution.client_upload_id` has a global non-empty unique constraint.
- The service already narrows duplicate lookup to `booking.campaign.tenant`.

Target:

- `tenant + client_upload_id` for non-empty upload ids

Recommended migration:

1. Add direct POE tenant ownership or another DB-supported tenant idempotency key.
2. Backfill from `booking.campaign.tenant`.
3. Add application validation.
4. Replace the global non-empty uniqueness constraint with tenant-scoped non-empty uniqueness.

## Alert Rules

Current:

- `AlertRule.metric` is globally unique even though rules now have a nullable tenant.

Target:

- one platform default per metric
- optional tenant override per `tenant + metric`

Recommended migration:

1. Decide whether platform defaults live in `AlertRule(tenant=NULL)` or a separate template model.
2. Add partial uniqueness for global defaults and tenant overrides.
3. Update evaluation to merge tenant override with platform default.
4. Preserve cooldown behavior per tenant.

## Saved Views And Dashboard Preferences

Current:

- `SavedOperationalView`: `user + company_name + name`
- `DashboardWidgetPreference`: `user + company_name + widget_key`

Target:

- `user + tenant + name`
- `user + tenant + widget_key`

Recommended migration:

1. Confirm all rows have tenant ownership.
2. Backfill tenant from user where missing.
3. Keep `company_name` as a display snapshot only.
4. Replace uniqueness constraints in a small observability migration.

## Import/Export Files

Current:

- job rows are tenant-owned
- stored paths live under `imports/` and `exports/`
- some generated filenames are job-specific; some export filenames are generic report names

Target:

- tenant/job namespaced storage paths for future generated reports

Recommended migration:

1. Preserve existing file paths.
2. For new generated files, include tenant slug and job id.
3. Keep download authorization tenant-scoped through `ImportExportJob.tenant`.
