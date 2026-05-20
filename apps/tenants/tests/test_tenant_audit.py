from django.test import SimpleTestCase

from apps.tenants.audit import (
    exposed_surfaces_requiring_scoping,
    models_requiring_tenant_ownership,
    uniqueness_constraints_requiring_redesign,
)


class TenantOwnershipAuditTests(SimpleTestCase):
    def test_audit_covers_core_operational_models(self):
        required_models = {
            "inventory.MediaSite",
            "inventory.MediaUnit",
            "campaigns.Campaign",
            "bookings.Booking",
            "poe.ProofOfExecution",
            "billing.Invoice",
            "billing.CampaignEstimate",
            "observability.ImportExportJob",
            "notifications.Notification",
        }

        self.assertTrue(required_models.issubset(set(models_requiring_tenant_ownership())))

    def test_audit_records_global_identifier_constraints(self):
        constraints = uniqueness_constraints_requiring_redesign()

        self.assertIn("inventory.MediaSite", constraints)
        self.assertIn("inventory.MediaUnit", constraints)
        self.assertIn("campaigns.Campaign", constraints)
        self.assertIn("billing.Invoice", constraints)
        self.assertIn("poe.ProofOfExecution", constraints)

    def test_audit_records_external_surfaces(self):
        surfaces = exposed_surfaces_requiring_scoping()

        self.assertIn("mobile upload", surfaces["poe.ProofOfExecution"])
        self.assertIn("operations dashboard", surfaces["observability.ImportExportJob"])
        self.assertIn("operational search", surfaces["campaigns.Campaign"])
