import io
import json

from django.core.management import call_command
from django.test import TestCase

from apps.billing.models import SupplierProfile
from apps.observability.models import ImportExportJob
from apps.tenants.identifier_audit import build_tenant_identifier_audit


class TenantIdentifierAuditTests(TestCase):
    def test_audit_reports_global_identifier_constraints_and_sequence_gaps(self):
        audit = build_tenant_identifier_audit()
        blockers = {item["key"]: item for item in audit["global_uniqueness_blockers"]}
        sequence_gaps = {item["key"]: item for item in audit["sequence_ownership_gaps"]}

        self.assertFalse(audit["constraints_changed"])
        self.assertFalse(audit["numbering_behavior_changed"])
        self.assertIn("media_site_code", blockers)
        self.assertIn("media_unit_code", blockers)
        self.assertIn("campaign_code", blockers)
        self.assertIn("invoice_number", blockers)
        self.assertIn("estimate_number", blockers)
        self.assertIn("poe_client_upload_id", blockers)
        self.assertIn("alert_rule_metric", blockers)
        self.assertIn("saved_operational_view_name", blockers)
        self.assertIn("dashboard_widget_preference_key", blockers)
        self.assertIn("invoice_sequence", sequence_gaps)
        self.assertIn("poe_client_upload_id_idempotency", sequence_gaps)

    def test_audit_reports_null_tenant_legacy_records(self):
        SupplierProfile.objects.create(
            legal_name="Legacy Supplier",
            gstin="27ZZZZZ0000Z1Z5",
            address_line_1="Legacy Road",
            city="Jammu",
            state="Jammu and Kashmir",
            postal_code="180001",
            state_code="01",
        )
        ImportExportJob.objects.create(
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
        )

        audit = build_tenant_identifier_audit()
        null_counts = {item["model"]: item["null_tenant_count"] for item in audit["null_tenant_records"]}

        self.assertGreaterEqual(null_counts["billing.SupplierProfile"], 1)
        self.assertGreaterEqual(null_counts["observability.ImportExportJob"], 1)

    def test_management_command_json_outputs_read_only_audit_payload(self):
        output = io.StringIO()

        call_command("audit_tenant_identifiers", "--format", "json", stdout=output)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["phase"], "1F")
        self.assertIn("global_uniqueness_blockers", payload)
        self.assertIn("identifier_targets", payload)
        self.assertIn("sequence_ownership_gaps", payload)

    def test_management_command_text_outputs_summary(self):
        output = io.StringIO()

        call_command("audit_tenant_identifiers", stdout=output)

        text = output.getvalue()
        self.assertIn("OMMS Tenant Identifier Audit - Phase 1F", text)
        self.assertIn("Identifier targets", text)
        self.assertIn("Sequence ownership gaps", text)
