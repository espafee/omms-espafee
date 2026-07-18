from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.billing.models import CampaignEstimate
from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.observability.models import AuditEvent
from apps.tenants.models import Tenant
from apps.users.models import User

from ..models import CampaignProposal, CampaignProposalLine, MediaPlannerShareLink
from ..services import (
    AvailabilityStatus,
    InventoryAvailabilityService,
    convert_proposal_to_campaign,
    create_estimate_from_proposal,
    submit_proposal,
)


class LiveMediaPlannerTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="North Media", slug="north-media", status=Tenant.Status.ACTIVE)
        self.other_tenant = Tenant.objects.create(name="South Media", slug="south-media", status=Tenant.Status.ACTIVE)
        self.admin = User.objects.create_user(
            email="admin@north.test", username="north-admin", password="secret", role=User.Role.ADMIN, tenant=self.tenant
        )
        self.client_user = User.objects.create_user(
            email="client@north.test", username="north-client", password="secret", role=User.Role.CLIENT,
            tenant=self.tenant, organization_name="Acme India",
        )
        self.other_client = User.objects.create_user(
            email="client@south.test", username="south-client", password="secret", role=User.Role.CLIENT,
            tenant=self.other_tenant,
        )
        self.site = MediaSite.objects.create(
            tenant=self.tenant, name="Central Junction", code="NORTH-SITE", site_type=MediaSite.SiteType.BILLBOARD,
            address="Central Road", city="Jammu", state="Jammu and Kashmir",
        )
        self.other_site = MediaSite.objects.create(
            tenant=self.other_tenant, name="South Junction", code="SOUTH-SITE", site_type=MediaSite.SiteType.BILLBOARD,
            address="South Road", city="Delhi", state="Delhi",
        )
        self.unit = self.make_unit(self.site, "NORTH-U1", public=True)
        self.private_unit = self.make_unit(self.site, "NORTH-PRIVATE", public=False)
        self.other_unit = self.make_unit(self.other_site, "SOUTH-U1", public=True)
        self.link, self.raw_token = MediaPlannerShareLink.create_with_token(
            tenant=self.tenant, created_by=self.admin, client=self.client_user, title="Acme Planner",
            show_rates=False, pricing_mode=MediaPlannerShareLink.PricingMode.HIDDEN,
        )
        self.api = APIClient()
        self.start = date.today() + timedelta(days=10)
        self.end = self.start + timedelta(days=10)

    def make_unit(self, site, code, *, public, status=MediaUnit.Status.AVAILABLE):
        return MediaUnit.objects.create(
            site=site, unit_code=code, face_count=1, width=Decimal("20.00"), height=Decimal("10.00"),
            monthly_rate=Decimal("50000.00"), facing_direction="North", site_type=MediaUnit.SiteType.SINGLE_SIDE,
            status=status, is_publicly_listed=public, public_description="Client-safe description",
            public_features=["High visibility"],
        )

    def proposal_payload(self, unit=None, **overrides):
        payload = {
            "campaign_name": "Summer Launch", "brand_company": "Acme India", "objective": "Awareness",
            "requested_start_date": self.start, "requested_end_date": self.end, "contact_name": "Client Contact",
            "contact_email": "client@example.test", "contact_phone": "9999999999", "notes": "Please review",
            "unit_public_ids": [(unit or self.unit).public_id], "idempotency_key": "request-1",
        }
        payload.update(overrides)
        return payload

    def submit(self, unit=None, **overrides):
        return submit_proposal(link=self.link, validated_data=self.proposal_payload(unit, **overrides))[0]

    def test_public_token_exposes_only_published_tenant_inventory_and_safe_fields(self):
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["meta"]["eligible_unit_count"], 1)
        self.assertEqual([row["unit_code"] for row in response.data["results"]], [self.unit.unit_code])
        serialized = response.data["results"][0]
        self.assertNotIn("id", serialized)
        self.assertNotIn("acquisition_cost", serialized)
        self.assertNotIn("margin", serialized)
        self.assertIsNone(serialized["monthly_rate"])

    def test_allowed_city_matching_is_trimmed_and_case_insensitive(self):
        for value in (["Jammu"], ["jammu"], [" Jammu "], "Jammu", "jammu", " Jammu ", "Jammu, Delhi"):
            with self.subTest(value=value):
                self.link.allowed_cities = value
                self.link.save(update_fields=["allowed_cities"])
                response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(response.data["filters"]["cities"], ["Jammu"])

    def test_existing_link_reflects_unpublished_to_published_transition(self):
        self.link.allowed_cities = "Jammu"
        self.link.save(update_fields=["allowed_cities"])
        initial_response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual([row["unit_code"] for row in initial_response.data["results"]], [self.unit.unit_code])
        self.assertNotIn(self.private_unit.unit_code, [row["unit_code"] for row in initial_response.data["results"]])

        self.api.force_authenticate(self.admin)
        publish_response = self.api.post(
            "/api/v1/inventory/units/bulk-publication/",
            {"unit_ids": [self.private_unit.id], "is_publicly_listed": True},
            format="json",
        )
        self.assertEqual(publish_response.status_code, 200)
        self.private_unit.refresh_from_db()
        self.assertTrue(self.private_unit.is_publicly_listed)

        self.api.force_authenticate(user=None)
        published_response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(published_response.status_code, 200)
        self.assertEqual(
            sorted(row["unit_code"] for row in published_response.data["results"]),
            sorted([self.unit.unit_code, self.private_unit.unit_code]),
        )

        self.api.force_authenticate(self.admin)
        unpublish_response = self.api.post(
            "/api/v1/inventory/units/bulk-publication/",
            {"unit_ids": [self.private_unit.id], "is_publicly_listed": False},
            format="json",
        )
        self.assertEqual(unpublish_response.status_code, 200)
        self.private_unit.refresh_from_db()
        self.assertFalse(self.private_unit.is_publicly_listed)

        self.api.force_authenticate(user=None)
        final_response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual([row["unit_code"] for row in final_response.data["results"]], [self.unit.unit_code])

    def test_internal_eligible_inventory_preview_reports_pipeline_counts(self):
        self.link.allowed_cities = "Jammu"
        self.link.save(update_fields=["allowed_cities"])
        self.api.force_authenticate(self.admin)
        response = self.api.get(f"/api/v1/planner/links/{self.link.id}/eligible-inventory/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["counts"]["base_media_units"], 3)
        self.assertEqual(response.data["counts"]["tenant_scoped"], 2)
        self.assertEqual(response.data["counts"]["publicly_listed"], 1)
        self.assertEqual(response.data["counts"]["allowed_city"], 1)
        self.assertEqual(response.data["counts"]["eligible"], 1)
        self.assertEqual(response.data["excluded"]["not_published"], 1)

    def test_public_facets_are_tenant_scoped_and_exclude_unpublished_units(self):
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["filters"]["cities"], ["Jammu"])
        self.assertEqual(response.data["filters"]["locations"], ["Central Junction"])
        self.assertEqual(response.data["filters"]["formats"], [MediaUnit.SiteType.SINGLE_SIDE])
        self.assertEqual(response.data["filters"]["facing_directions"], ["North"])
        self.assertNotIn("Delhi", response.data["filters"]["cities"])
        self.assertNotIn(self.private_unit.unit_code, str(response.data["filters"]))

    def test_valid_link_with_zero_eligible_units_reports_zero_count(self):
        self.link.allowed_cities = ["No Published City"]
        self.link.save(update_fields=["allowed_cities"])
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["meta"]["eligible_unit_count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_public_filter_names_match_endpoint_and_remain_tenant_scoped(self):
        response = self.api.get(
            f"/api/v1/public/media-planner/{self.raw_token}/",
            {
                "city": " jammu ",
                "location": "central junction",
                "display_format": MediaUnit.SiteType.SINGLE_SIDE.value,
                "facing": "north",
                "illumination": "false",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["unit_code"], self.unit.unit_code)

    def test_date_and_availability_filters_return_correct_results(self):
        campaign = Campaign.objects.create(
            tenant=self.tenant, client=self.client_user, account_manager=self.admin, name="Booked", code="BOOKED-FILTER",
            start_date=self.start, end_date=self.end, budget=Decimal("50000"), status=Campaign.Status.ACTIVE,
        )
        Booking.objects.create(
            campaign=campaign, media_unit=self.unit, start_date=self.start, end_date=self.end,
            booked_rate=Decimal("50000"), status=Booking.Status.CONFIRMED,
        )
        available_response = self.api.get(
            f"/api/v1/public/media-planner/{self.raw_token}/",
            {"start_date": self.start.isoformat(), "end_date": self.end.isoformat(), "availability": "available"},
        )
        booked_response = self.api.get(
            f"/api/v1/public/media-planner/{self.raw_token}/",
            {"start_date": self.start.isoformat(), "end_date": self.end.isoformat(), "availability": "booked"},
        )
        self.assertEqual(available_response.status_code, 200)
        self.assertEqual(available_response.data["count"], 0)
        self.assertEqual(booked_response.status_code, 200)
        self.assertEqual(booked_response.data["count"], 1)

    def test_internal_link_creation_reports_eligible_unit_count(self):
        self.api.force_authenticate(self.admin)
        response = self.api.post(
            "/api/v1/planner/links/",
            {
                "title": "Zero Link",
                "pricing_mode": MediaPlannerShareLink.PricingMode.HIDDEN,
                "show_rates": False,
                "allowed_cities": ["No Published City"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["eligible_unit_count"], 0)

    def test_revoked_and_expired_links_fail_safely(self):
        self.link.revoked_at = timezone.now()
        self.link.save(update_fields=["revoked_at"])
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(response.status_code, 410)
        self.link.revoked_at = None
        self.link.expires_at = timezone.now() - timedelta(seconds=1)
        self.link.save(update_fields=["revoked_at", "expires_at"])
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(response.status_code, 410)

    def test_inclusive_date_overlap_and_partial_overlap_are_blocked(self):
        campaign = Campaign.objects.create(
            tenant=self.tenant, client=self.client_user, account_manager=self.admin, name="Booked", code="BOOKED-CMP",
            start_date=self.start, end_date=self.end, budget=Decimal("50000"), status=Campaign.Status.ACTIVE,
        )
        Booking.objects.create(
            campaign=campaign, media_unit=self.unit, start_date=self.end, end_date=self.end + timedelta(days=3),
            booked_rate=Decimal("50000"), status=Booking.Status.CONFIRMED,
        )
        result = InventoryAvailabilityService().resolve(self.unit, start_date=self.start, end_date=self.end)
        self.assertEqual(result["status"], AvailabilityStatus.PARTIALLY_AVAILABLE)
        boundary = InventoryAvailabilityService().resolve(self.unit, start_date=self.end, end_date=self.end)
        self.assertEqual(boundary["status"], AvailabilityStatus.BOOKED)

    def test_maintenance_and_reserved_units_are_unavailable(self):
        maintenance = self.make_unit(self.site, "NORTH-MAINT", public=True, status=MediaUnit.Status.MAINTENANCE)
        reserved = self.make_unit(self.site, "NORTH-HOLD", public=True, status=MediaUnit.Status.RESERVED)
        self.assertEqual(InventoryAvailabilityService().resolve(maintenance)["status"], AvailabilityStatus.UNDER_MAINTENANCE)
        self.assertEqual(InventoryAvailabilityService().resolve(reserved)["status"], AvailabilityStatus.ON_HOLD)

    def test_rate_is_only_returned_for_standard_visible_pricing(self):
        self.link.show_rates = True
        self.link.pricing_mode = MediaPlannerShareLink.PricingMode.STANDARD_SELLING_RATE
        self.link.save(update_fields=["show_rates", "pricing_mode"])
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertEqual(response.data["results"][0]["monthly_rate"], "50000.00")
        self.link.pricing_mode = MediaPlannerShareLink.PricingMode.CLIENT_RATE_CARD
        self.link.save(update_fields=["pricing_mode"])
        response = self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        self.assertIsNone(response.data["results"][0]["monthly_rate"])

    def test_submission_snapshots_data_does_not_create_booking_and_is_idempotent(self):
        proposal, created = submit_proposal(link=self.link, validated_data=self.proposal_payload())
        second, second_created = submit_proposal(link=self.link, validated_data=self.proposal_payload())
        self.assertTrue(created)
        self.assertFalse(second_created)
        self.assertEqual(second.id, proposal.id)
        self.assertEqual(Booking.objects.count(), 0)
        line = proposal.lines.get()
        self.assertEqual(line.unit_code, self.unit.unit_code)
        self.assertEqual(line.location_name, self.site.name)
        self.assertEqual(line.monthly_rate_snapshot, Decimal("50000.00"))
        self.assertEqual(line.availability_snapshot["status"], AvailabilityStatus.AVAILABLE)

    def test_submission_rejects_cross_tenant_and_unpublished_units(self):
        with self.assertRaises(ValidationError):
            self.submit(self.other_unit)
        with self.assertRaises(ValidationError):
            self.submit(self.private_unit, idempotency_key="request-2")

    def test_public_submission_never_accepts_client_price_or_booking_state(self):
        response = self.api.post(
            f"/api/v1/public/media-planner/{self.raw_token}/proposals/",
            {**self.proposal_payload(), "unit_public_ids": [str(self.unit.public_id)], "monthly_rate": "1.00", "status": "confirmed"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.count(), 0)
        self.assertEqual(CampaignProposal.objects.get().status, CampaignProposal.Status.SUBMITTED)

    def test_estimate_preserves_tenant_client_and_existing_numbering(self):
        proposal = self.submit()
        estimate, created = create_estimate_from_proposal(proposal=proposal, actor=self.admin)
        self.assertTrue(created)
        self.assertEqual(estimate.client, self.client_user)
        self.assertTrue(estimate.estimate_number.startswith("EST/"))
        self.assertEqual(proposal.tenant, estimate.client.tenant)
        self.assertEqual(estimate.lines.count(), 1)

    def test_estimate_response_synchronizes_proposal_status(self):
        proposal = self.submit()
        estimate, _ = create_estimate_from_proposal(proposal=proposal, actor=self.admin)
        from apps.billing.services import CampaignEstimateService

        service = CampaignEstimateService()
        service.share(estimate, actor=self.admin)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, CampaignProposal.Status.SENT_TO_CLIENT)
        service.approve(estimate, comment="Approved")
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, CampaignProposal.Status.CLIENT_APPROVED)

    def test_conversion_revalidates_and_is_idempotent(self):
        proposal = self.submit()
        estimate, _ = create_estimate_from_proposal(proposal=proposal, actor=self.admin)
        estimate.status = CampaignEstimate.Status.APPROVED
        estimate.save(update_fields=["status"])
        proposal.status = CampaignProposal.Status.CLIENT_APPROVED
        proposal.save(update_fields=["status"])
        campaign, created = convert_proposal_to_campaign(proposal=proposal, actor=self.admin, campaign_code="PLANNER-CMP")
        proposal.refresh_from_db()
        second, second_created = convert_proposal_to_campaign(proposal=proposal, actor=self.admin, campaign_code="IGNORED")
        self.assertTrue(created)
        self.assertFalse(second_created)
        self.assertEqual(second, campaign)
        self.assertEqual(Booking.objects.filter(campaign=campaign, status=Booking.Status.PENDING).count(), 1)
        self.assertEqual(proposal.status, CampaignProposal.Status.CONVERTED_TO_CAMPAIGN)

    def test_conversion_is_transactional_when_booking_creation_fails(self):
        second_unit = self.make_unit(self.site, "NORTH-U2", public=True)
        proposal = self.submit(unit_public_ids=[self.unit.public_id, second_unit.public_id])
        estimate, _ = create_estimate_from_proposal(proposal=proposal, actor=self.admin)
        estimate.status = CampaignEstimate.Status.APPROVED
        estimate.save(update_fields=["status"])
        proposal.status = CampaignProposal.Status.CLIENT_APPROVED
        proposal.save(update_fields=["status"])
        original_create = __import__("apps.bookings.services", fromlist=["BookingService"]).BookingService.create
        calls = {"count": 0}

        def fail_second(service, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise ValidationError("Simulated booking failure")
            return original_create(service, *args, **kwargs)

        with patch("apps.planner.services.BookingService.create", new=fail_second), self.assertRaises(ValidationError):
            convert_proposal_to_campaign(proposal=proposal, actor=self.admin, campaign_code="ROLLBACK-CMP")
        self.assertFalse(Campaign.objects.filter(code="ROLLBACK-CMP").exists())
        self.assertFalse(Booking.objects.exists())

    def test_conversion_refuses_new_availability_conflict(self):
        proposal = self.submit()
        estimate, _ = create_estimate_from_proposal(proposal=proposal, actor=self.admin)
        estimate.status = CampaignEstimate.Status.APPROVED
        estimate.save(update_fields=["status"])
        proposal.status = CampaignProposal.Status.CLIENT_APPROVED
        proposal.save(update_fields=["status"])
        blocker = Campaign.objects.create(
            tenant=self.tenant, client=self.client_user, name="Blocker", code="BLOCKER-CMP", start_date=self.start,
            end_date=self.end, budget=Decimal("50000"), status=Campaign.Status.ACTIVE,
        )
        Booking.objects.create(campaign=blocker, media_unit=self.unit, start_date=self.start, end_date=self.end, booked_rate=Decimal("50000"), status=Booking.Status.CONFIRMED)
        with self.assertRaises(ValidationError):
            convert_proposal_to_campaign(proposal=proposal, actor=self.admin, campaign_code="CONFLICT-CMP")

    def test_audit_events_cover_link_open_submission_estimate_and_conversion(self):
        self.api.get(f"/api/v1/public/media-planner/{self.raw_token}/")
        proposal = self.submit()
        estimate, _ = create_estimate_from_proposal(proposal=proposal, actor=self.admin)
        estimate.status = CampaignEstimate.Status.APPROVED
        estimate.save(update_fields=["status"])
        proposal.status = CampaignProposal.Status.CLIENT_APPROVED
        proposal.save(update_fields=["status"])
        convert_proposal_to_campaign(proposal=proposal, actor=self.admin, campaign_code="AUDIT-CMP")
        events = set(AuditEvent.objects.filter(entity_id=proposal.id).values_list("event_type", flat=True))
        self.assertTrue({"planner.proposal.submitted", "planner.proposal.estimate_created", "planner.proposal.converted"}.issubset(events))


class MediaPlannerPlatformDiagnosticsTests(TestCase):
    endpoint = "/api/v1/platform/diagnostics/media-planner/"

    def setUp(self):
        self.platform_tenant = Tenant.objects.create(
            name="OMMS Platform",
            slug="omms-platform-test",
            tenant_type=Tenant.TenantType.PLATFORM,
            status=Tenant.Status.ACTIVE,
        )
        self.tenant = Tenant.objects.create(name="ESPA FEE", slug="espa-fee", status=Tenant.Status.ACTIVE)
        self.other_tenant = Tenant.objects.create(name="Other Media", slug="other-media", status=Tenant.Status.ACTIVE)
        self.platform_admin = User.objects.create_superuser(
            email="platform@omms.test",
            username="platform",
            password="secret",
            tenant=self.platform_tenant,
        )
        self.company_admin = User.objects.create_user(
            email="admin@espa.test",
            username="espa-admin",
            password="secret",
            role=User.Role.ADMIN,
            tenant=self.tenant,
        )
        self.user = User.objects.create_user(
            email="ops@espa.test",
            username="espa-ops",
            password="secret",
            role=User.Role.OPERATIONS,
            tenant=self.tenant,
        )
        self.site = MediaSite.objects.create(
            tenant=self.tenant,
            name="SIDCO Chowk",
            code="ESPA-SITE",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Canal Road",
            city="Jammu",
            state="Jammu and Kashmir",
        )
        self.other_site = MediaSite.objects.create(
            tenant=self.other_tenant,
            name="Other Chowk",
            code="OTHER-SITE",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Other Road",
            city="Delhi",
            state="Delhi",
        )
        self.published_unit = self.make_unit(self.site, "ESPA-001", public=True)
        self.unpublished_unit = self.make_unit(self.site, "ESPA-002_1", public=False)
        self.other_unit = self.make_unit(self.other_site, "OTHER-001", public=True)
        self.link, self.raw_token = MediaPlannerShareLink.create_with_token(
            tenant=self.tenant,
            created_by=self.company_admin,
            title="Live Media Planner",
            allowed_cities="Jammu",
            pricing_mode=MediaPlannerShareLink.PricingMode.HIDDEN,
        )
        self.api = APIClient()

    def make_unit(self, site, code, *, public, status=MediaUnit.Status.AVAILABLE):
        return MediaUnit.objects.create(
            site=site,
            unit_code=code,
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            monthly_rate=Decimal("50000.00"),
            status=status,
            site_type=MediaUnit.SiteType.SINGLE_SIDE,
            is_publicly_listed=public,
            public_description="Safe public text",
            public_features=["Visible"],
        )

    @override_settings(ENABLE_PLATFORM_DIAGNOSTICS=True)
    def test_diagnostics_requires_authentication(self):
        response = self.api.get(self.endpoint, {"planner_link_id": self.link.id})
        self.assertEqual(response.status_code, 401)

    @override_settings(ENABLE_PLATFORM_DIAGNOSTICS=True)
    def test_diagnostics_allows_only_platform_superadmin(self):
        self.api.force_authenticate(self.company_admin)
        company_response = self.api.get(self.endpoint, {"planner_link_id": self.link.id})
        self.assertEqual(company_response.status_code, 403)

        self.api.force_authenticate(self.user)
        user_response = self.api.get(self.endpoint, {"planner_link_id": self.link.id})
        self.assertEqual(user_response.status_code, 403)

        self.api.force_authenticate(self.platform_admin)
        platform_response = self.api.get(self.endpoint, {"planner_link_id": self.link.id})
        self.assertEqual(platform_response.status_code, 200)

    @override_settings(ENABLE_PLATFORM_DIAGNOSTICS=False)
    def test_diagnostics_feature_flag_disables_endpoint(self):
        self.api.force_authenticate(self.platform_admin)
        response = self.api.get(self.endpoint, {"planner_link_id": self.link.id})
        self.assertEqual(response.status_code, 404)

    @override_settings(
        ENABLE_PLATFORM_DIAGNOSTICS=True,
        OMMS_GIT_COMMIT="abcdef1234567890",
        OMMS_BUILD_TIMESTAMP="2026-07-18T07:00:00Z",
        OMMS_ENVIRONMENT_NAME="test",
    )
    def test_diagnostics_returns_safe_pipeline_evidence_without_secrets(self):
        self.api.force_authenticate(self.platform_admin)
        response = self.api.get(
            self.endpoint,
            {
                "planner_link_id": self.link.id,
                "unit_code": "ESPA-001,ESPA-002_1,OTHER-001",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.data
        self.assertEqual(payload["service"]["git_sha"], "abcdef123456")
        self.assertEqual(payload["service"]["environment"], "test")
        self.assertEqual(payload["planner_link"]["allowed_cities_raw_type"], "str")
        self.assertEqual(payload["planner_link"]["allowed_cities_safe_summary"], ["Jammu"])
        self.assertEqual(payload["pipeline"]["tenant_units"], 2)
        self.assertEqual(payload["pipeline"]["publicly_listed"], 1)
        self.assertEqual(payload["pipeline"]["allowed_city_eligible"], 1)
        self.assertEqual(payload["pipeline"]["final_serialized"], 1)
        self.assertEqual(payload["exclusions"]["unpublished"], 1)
        self.assertEqual(payload["exclusions"]["wrong_tenant"], 1)
        self.assertTrue(payload["database"]["migration_status"]["inventory.0009_mediaunit_is_publicly_listed_and_more"])
        self.assertTrue(payload["database"]["migration_status"]["planner.0001_initial"])
        self.assertRegex(payload["database"]["database_fingerprint"], r"^[a-f0-9]{16}$")

        serialized_payload = str(payload)
        self.assertNotIn(self.raw_token, serialized_payload)
        self.assertNotIn(self.link.token_hash, serialized_payload)
        self.assertNotIn("DATABASE_URL", serialized_payload)
        self.assertNotIn("SECRET_KEY", serialized_payload)
        self.assertNotIn("monthly_rate", serialized_payload)

    @override_settings(ENABLE_PLATFORM_DIAGNOSTICS=True)
    def test_diagnostics_requires_planner_identifier(self):
        self.api.force_authenticate(self.platform_admin)
        response = self.api.get(self.endpoint)
        self.assertEqual(response.status_code, 400)

    @override_settings(ENABLE_PLATFORM_DIAGNOSTICS=True)
    def test_diagnostics_unit_sampling_is_limited(self):
        for index in range(30):
            self.make_unit(self.site, f"ESPA-BULK-{index}", public=True)
        self.api.force_authenticate(self.platform_admin)
        response = self.api.get(self.endpoint, {"planner_link_id": self.link.id})
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.data["units"]), 25)
