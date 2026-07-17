from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.campaigns.models import Campaign, CampaignAccessToken
from apps.tenants.models import Tenant

User = get_user_model()


class CampaignLifecycleTests(APITestCase):
    def setUp(self):
        self.today = date(2026, 5, 15)
        self.tenant = Tenant.objects.create(name="Lifecycle Outdoor", slug="lifecycle-outdoor")
        self.other_tenant = Tenant.objects.create(name="Other Outdoor", slug="other-lifecycle-outdoor")
        self.admin = self._user("lifecycle-admin@omms.test", "lifecycle_admin", self.tenant, User.Role.ADMIN)
        self.client_user = self._user("lifecycle-client@omms.test", "lifecycle_client", self.tenant, User.Role.CLIENT)
        self.other_client = self._user("other-client@omms.test", "other_lifecycle_client", self.other_tenant, User.Role.CLIENT)

    def _user(self, email, username, tenant, role):
        return User.objects.create_user(
            email=email,
            username=username,
            password="TestPass123!",
            tenant=tenant,
            role=role,
        )

    def _campaign(self, code, start_date, end_date, status_value=Campaign.Status.ACTIVE, tenant=None, client=None):
        tenant = tenant or self.tenant
        return Campaign.objects.create(
            name=f"Campaign {code}",
            code=code,
            tenant=tenant,
            client=client or self.client_user,
            account_manager=self.admin if tenant == self.tenant else None,
            start_date=start_date,
            end_date=end_date,
            budget=Decimal("100000.00"),
            status=status_value,
        )

    def test_date_derived_lifecycle_and_boundary_dates(self):
        ended = self._campaign("LIFE-ENDED", self.today - timedelta(days=10), self.today - timedelta(days=1))
        ongoing = self._campaign("LIFE-ONGOING", self.today - timedelta(days=1), self.today + timedelta(days=1))
        upcoming = self._campaign("LIFE-UPCOMING", self.today + timedelta(days=1), self.today + timedelta(days=10))
        boundary = self._campaign("LIFE-BOUNDARY", self.today - timedelta(days=2), self.today)

        self.assertEqual(ended.effective_status_at(self.today), Campaign.EffectiveStatus.ENDED)
        self.assertEqual(ongoing.effective_status_at(self.today), Campaign.EffectiveStatus.ONGOING)
        self.assertEqual(upcoming.effective_status_at(self.today), Campaign.EffectiveStatus.UPCOMING)
        self.assertEqual(boundary.effective_status_at(self.today), Campaign.EffectiveStatus.ONGOING)
        self.assertEqual(boundary.effective_status_at(self.today + timedelta(days=1)), Campaign.EffectiveStatus.ENDED)

    def test_cancelled_and_paused_override_date_lifecycle(self):
        cancelled = self._campaign(
            "LIFE-CANCELLED",
            self.today - timedelta(days=2),
            self.today + timedelta(days=2),
            Campaign.Status.CANCELLED,
        )
        paused = self._campaign(
            "LIFE-PAUSED",
            self.today - timedelta(days=2),
            self.today + timedelta(days=2),
            Campaign.Status.PAUSED,
        )

        self.assertEqual(cancelled.effective_status_at(self.today), Campaign.EffectiveStatus.CANCELLED)
        self.assertEqual(paused.effective_status_at(self.today), Campaign.EffectiveStatus.PAUSED)

    def test_local_date_uses_tenant_timezone(self):
        self.tenant.metadata = {"timezone": "Pacific/Kiritimati"}
        self.tenant.save(update_fields=["metadata", "updated_at"])
        campaign = self._campaign("LIFE-TIMEZONE", self.today, self.today)
        instant = datetime.fromisoformat("2026-05-14T12:30:00+00:00")

        with patch("apps.campaigns.models.timezone.now", return_value=instant):
            self.assertEqual(campaign.local_date(), self.today)
            self.assertEqual(campaign.effective_status, Campaign.EffectiveStatus.ONGOING)

    def test_api_filters_effective_status_and_preserves_tenant_isolation(self):
        today = timezone.localdate()
        own_ended = self._campaign("API-OWN-ENDED", today - timedelta(days=10), today - timedelta(days=1))
        self._campaign("API-OWN-ONGOING", today - timedelta(days=1), today + timedelta(days=1))
        other_ended = self._campaign(
            "API-OTHER-ENDED",
            today - timedelta(days=10),
            today - timedelta(days=1),
            tenant=self.other_tenant,
            client=self.other_client,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("campaigns-list"), {"effective_status": "ENDED"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertIn(own_ended.id, ids)
        self.assertNotIn(other_ended.id, ids)
        self.assertTrue(all(item["effective_status"] == Campaign.EffectiveStatus.ENDED for item in response.data["results"]))

    def test_api_uses_latest_first_deterministic_ordering(self):
        today = timezone.localdate()
        first = self._campaign("ORDER-FIRST", today, today + timedelta(days=2))
        second = self._campaign("ORDER-SECOND", today, today + timedelta(days=2))
        created_at = timezone.make_aware(datetime(2026, 5, 1, 12, 0))
        Campaign.objects.filter(id__in=[first.id, second.id]).update(created_at=created_at)
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("campaigns-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ordered_ids = [item["id"] for item in response.data["results"] if item["id"] in {first.id, second.id}]
        self.assertEqual(ordered_ids, [second.id, first.id])

    def test_ended_campaign_internal_detail_is_independent_of_public_link_state(self):
        today = timezone.localdate()
        campaign = self._campaign("ENDED-INTERNAL", today - timedelta(days=10), today - timedelta(days=1))
        _, raw_token = CampaignAccessToken.create_with_token(campaign=campaign, created_by=self.admin)
        self.client.force_authenticate(user=self.admin)

        internal_response = self.client.get(reverse("campaigns-detail", args=[campaign.id]))
        access_links_response = self.client.get(reverse("campaign-access-links-list"))
        self.client.force_authenticate(user=None)
        public_response = self.client.get(reverse("campaigns-public-detail", args=[raw_token]))

        self.assertEqual(internal_response.status_code, status.HTTP_200_OK)
        self.assertEqual(internal_response.data["effective_status"], Campaign.EffectiveStatus.ENDED)
        self.assertEqual(access_links_response.status_code, status.HTTP_200_OK)
        self.assertEqual(access_links_response.data["results"][0]["link_status"], "ended")
        self.assertEqual(public_response.status_code, status.HTTP_410_GONE)
        self.assertEqual(public_response.data["code"], "campaign_ended")
