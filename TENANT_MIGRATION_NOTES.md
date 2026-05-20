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
