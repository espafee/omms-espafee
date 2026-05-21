# Tenant Identifier Audit Local Result

Run date: 2026-05-21

Project path: `/Users/macbook/Projects/OMMS`

Commands run:

```bash
/Users/macbook/Projects/OMMS/.venv312/bin/python manage.py audit_tenant_identifiers
/Users/macbook/Projects/OMMS/.venv312/bin/python manage.py audit_tenant_identifiers --format json
```

## Summary

| Check | Result |
| --- | --- |
| Constraints changed | `False` |
| Numbering behavior changed | `False` |
| Duplicate identifier groups | `0` |
| Null-tenant records | `0` across audited paths |
| Sequence ownership gaps | `5` expected planning gaps |

## Identifier Target Results

| Identifier | Records | Null tenant | Duplicate groups |
| --- | ---: | ---: | ---: |
| `inventory.MediaSite.code` | 0 | 0 | 0 |
| `inventory.MediaUnit.unit_code` | 0 | 0 | 0 |
| `campaigns.Campaign.code` | 0 | 0 | 0 |
| `billing.Invoice.invoice_number` | 0 | 0 | 0 |
| `billing.CampaignEstimate.estimate_number` | 0 | 0 | 0 |
| `poe.ProofOfExecution.client_upload_id` | 0 | 0 | 0 |
| `billing.SupplierProfile.gstin` | 0 | 0 | 0 |
| `observability.AlertRule.metric` | 0 | 0 | 0 |
| `observability.SavedOperationalView.name` | 0 | 0 | 0 |
| `observability.DashboardWidgetPreference.widget_key` | 0 | 0 | 0 |

## Null-Tenant Checks

All audited direct and derived tenant paths returned `0` null-tenant records locally:

- `inventory.MediaSite.tenant`
- `campaigns.Campaign.tenant`
- `billing.SupplierProfile.tenant`
- `billing.Invoice.campaign.tenant`
- `billing.CampaignEstimate.client.tenant`
- `billing.CampaignEstimate.campaign.tenant`
- `poe.ProofOfExecution.booking.campaign.tenant`
- `observability.ImportExportJob.tenant`
- `notifications.Notification.tenant`
- `notifications.EmailNotificationLog.tenant`
- `notifications.NotificationPreference.user.tenant`
- `observability.AlertRule.tenant`
- `observability.AlertEvent.tenant`
- `observability.SavedOperationalView.tenant`
- `observability.DashboardWidgetPreference.tenant`

## Expected Sequence Ownership Gaps

The audit correctly reported the known Phase 1G planning gaps:

1. `billing.InvoiceSequence` is still globally keyed by `document_type + financial_year`.
2. `billing.Invoice.invoice_number` allocation still uses the global invoice sequence.
3. `billing.CampaignEstimate.estimate_number` still uses a global primary-key based number shape.
4. `poe.ProofOfExecution.client_upload_id` service lookup is tenant-aware, but database uniqueness is still global.
5. `observability.ImportExportJob` generated report/export storage paths should become tenant/job namespaced later.

## Local Readiness

Local development is ready for Phase 1G planning, but not for automatic constraint migration. Production audit output must be captured and reviewed before any uniqueness or sequence migration is designed.

