from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bookings.models import Assignment, Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.issues.models import Issue
from apps.poe.models import ProofOfExecution
from apps.tenants.models import Tenant

User = get_user_model()


class DerivedTenantScopingTests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.platform_tenant = Tenant.objects.get(slug="omms-platform")
        self.alpha = Tenant.objects.create(name="Alpha Outdoor", slug="alpha-derived")
        self.beta = Tenant.objects.create(name="Beta Media", slug="beta-derived")
        self.platform_admin = User.objects.create_superuser(
            email="platform-derived@omms.test",
            username="platform_derived",
            password=self.password,
            tenant=self.platform_tenant,
        )
        self.alpha_admin = self._user("alpha-admin-derived@omms.test", "alpha_admin_derived", User.Role.ADMIN, self.alpha)
        self.beta_admin = self._user("beta-admin-derived@omms.test", "beta_admin_derived", User.Role.ADMIN, self.beta)
        self.alpha_field = self._user("alpha-field-derived@omms.test", "alpha_field_derived", User.Role.FIELD_STAFF, self.alpha)
        self.beta_field = self._user("beta-field-derived@omms.test", "beta_field_derived", User.Role.FIELD_STAFF, self.beta)
        self.alpha_client = self._user("alpha-client-derived@omms.test", "alpha_client_derived", User.Role.CLIENT, self.alpha)
        self.beta_client = self._user("beta-client-derived@omms.test", "beta_client_derived", User.Role.CLIENT, self.beta)
        self.alpha_site = self._site("Alpha Derived Site", "ALPHA-DER-SITE", self.alpha_admin, self.alpha)
        self.beta_site = self._site("Beta Derived Site", "BETA-DER-SITE", self.beta_admin, self.beta)
        self.alpha_unit = self._unit(self.alpha_site, "ALPHA-DER-UNIT")
        self.beta_unit = self._unit(self.beta_site, "BETA-DER-UNIT")
        self.alpha_campaign = self._campaign("Alpha Derived Campaign", "ALPHA-DER-CMP", self.alpha_client, self.alpha_admin, self.alpha)
        self.beta_campaign = self._campaign("Beta Derived Campaign", "BETA-DER-CMP", self.beta_client, self.beta_admin, self.beta)
        self.alpha_booking = self._booking(self.alpha_campaign, self.alpha_unit)
        self.beta_booking = self._booking(self.beta_campaign, self.beta_unit)
        Assignment.objects.create(booking=self.alpha_booking, user=self.alpha_field, assigned_by=self.alpha_admin)
        Assignment.objects.create(booking=self.beta_booking, user=self.beta_field, assigned_by=self.beta_admin)
        self.alpha_poe = self._poe(self.alpha_booking, ProofOfExecution.VerificationStatus.SUSPICIOUS)
        self.beta_poe = self._poe(self.beta_booking, ProofOfExecution.VerificationStatus.SUSPICIOUS)
        self.alpha_issue = self._issue(self.alpha_booking, self.alpha_field)
        self.beta_issue = self._issue(self.beta_booking, self.beta_field)

    def _user(self, email, username, role, tenant):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            tenant=tenant,
        )

    def _site(self, name, code, owner, tenant):
        return MediaSite.objects.create(
            name=name,
            code=code,
            tenant=tenant,
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Tenant Road",
            city="Jammu",
            state="Jammu and Kashmir",
            owner=owner,
        )

    def _unit(self, site, code):
        return MediaUnit.objects.create(
            site=site,
            unit_code=code,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            monthly_rate=Decimal("25000.00"),
            status=MediaUnit.Status.AVAILABLE,
        )

    def _campaign(self, name, code, client, manager, tenant):
        return Campaign.objects.create(
            name=name,
            code=code,
            tenant=tenant,
            client=client,
            account_manager=manager,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
        )

    def _booking(self, campaign, unit):
        return Booking.objects.create(
            campaign=campaign,
            media_unit=unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            booked_rate=Decimal("25000.00"),
            status=Booking.Status.CONFIRMED,
        )

    def _poe(self, booking, verification_status):
        return ProofOfExecution.objects.create(
            booking=booking,
            executed_on=date.today(),
            captured_at=timezone.now(),
            verification_status=verification_status,
        )

    def _issue(self, booking, reported_by):
        return Issue.objects.create(
            booking=booking,
            reported_by=reported_by,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.DAMAGE,
            description="Tenant-scoped issue",
            priority=Issue.Priority.MEDIUM,
        )

    def _result_ids(self, response):
        rows = response.data.get("results", response.data)
        return {row["id"] for row in rows}

    def test_booking_list_and_detail_are_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_admin)

        listing = self.client.get(reverse("bookings-list"))
        beta_detail = self.client.get(reverse("bookings-detail", args=[self.beta_booking.id]))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_booking.id, self._result_ids(listing))
        self.assertNotIn(self.beta_booking.id, self._result_ids(listing))
        self.assertEqual(beta_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_platform_admin_can_access_cross_tenant_bookings(self):
        self.client.force_authenticate(user=self.platform_admin)

        alpha_detail = self.client.get(reverse("bookings-detail", args=[self.alpha_booking.id]))
        beta_detail = self.client.get(reverse("bookings-detail", args=[self.beta_booking.id]))

        self.assertEqual(alpha_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(beta_detail.status_code, status.HTTP_200_OK)

    def test_booking_create_rejects_cross_tenant_campaign_and_unit(self):
        self.client.force_authenticate(user=self.alpha_admin)

        response = self.client.post(
            reverse("bookings-list"),
            {
                "campaign": self.alpha_campaign.id,
                "media_unit": self.beta_unit.id,
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=4),
                "booked_rate": "12000.00",
                "status": Booking.Status.CONFIRMED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_poe_queue_and_detail_are_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_admin)

        listing = self.client.get(reverse("poe-list"))
        beta_detail = self.client.get(reverse("poe-detail", args=[self.beta_poe.id]))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_poe.id, self._result_ids(listing))
        self.assertNotIn(self.beta_poe.id, self._result_ids(listing))
        self.assertEqual(beta_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_issue_list_and_detail_are_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_admin)

        listing = self.client.get(reverse("issues-list"))
        beta_detail = self.client.get(reverse("issues-detail", args=[self.beta_issue.id]))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_issue.id, self._result_ids(listing))
        self.assertNotIn(self.beta_issue.id, self._result_ids(listing))
        self.assertEqual(beta_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_mobile_assigned_work_is_tenant_and_assignment_scoped(self):
        self.client.force_authenticate(user=self.alpha_field)

        response = self.client.get(reverse("mobile-assigned-work"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking_ids = {row["booking_id"] for row in response.data}
        self.assertEqual(booking_ids, {self.alpha_booking.id})

    def test_mobile_admin_overview_is_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_admin)

        response = self.client.get(reverse("mobile-admin-overview"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_campaigns"], 1)
        self.assertEqual(response.data["suspicious_poe"], 1)

    def test_operations_summary_poe_metrics_are_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_admin)

        response = self.client.get(reverse("observability-operations-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["poe"]["suspicious_count"], 1)
        self.assertEqual(response.data["kpis"]["suspicious_poes"], 1)
