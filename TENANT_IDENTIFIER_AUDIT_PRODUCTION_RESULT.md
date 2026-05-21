# Tenant Identifier Audit Production Result

Run date: 2026-05-21

Target service:

- Backend: `https://omms-backend.onrender.com`
- Expected Render project root: `/opt/render/project/src`

## Execution Status

Production audit was **not executed from this Codex environment**.

Reason:

- No Render CLI executable is available locally.
- No authenticated Render shell/session is available in this environment.
- No production `DATABASE_URL` or Render service credentials are available locally.
- Public backend endpoints cannot execute Django management commands.

This result does not indicate a production data problem. It means Phase 1G remains blocked by production audit access until an authorized operator runs the read-only command in Render.

## Commands That Still Need To Run In Production

From the Render backend shell for the OMMS backend service:

```bash
cd /opt/render/project/src
python manage.py audit_tenant_identifiers
python manage.py audit_tenant_identifiers --format json
```

Recommended capture:

```bash
python manage.py audit_tenant_identifiers --format json > tenant_identifier_audit_production_$(date +%Y%m%d_%H%M%S).json
```

If Render shell output cannot be persisted, copy the JSON output into secure deployment notes and update this file with sanitized counts.

## Local Comparison Baseline

| Check | Local result | Production result |
| --- | --- | --- |
| Constraints changed | `False` | Pending |
| Numbering behavior changed | `False` | Pending |
| Duplicate identifier groups | `0` | Pending |
| Null-tenant records | `0` | Pending |
| Sequence ownership gaps | `5` expected gaps | Pending |

## Phase 1G Status

Phase 1G is **NO-GO** until production output is captured and reviewed.

Do not change:

- `MediaSite.code` uniqueness
- `MediaUnit.unit_code` uniqueness
- `Campaign.code` uniqueness
- `Invoice.invoice_number` uniqueness
- `InvoiceSequence` ownership/uniqueness
- `CampaignEstimate.estimate_number` uniqueness
- `ProofOfExecution.client_upload_id` uniqueness
- `AlertRule.metric` uniqueness
- saved-view/dashboard-preference uniqueness

## Manual Review Notes

When production output is available, update this document with:

- total duplicate groups
- duplicate groups by identifier target
- null-tenant counts by model/path
- whether sequence ownership gaps are expected only
- reviewer sign-off for platform, finance, operations, and deployment owners
