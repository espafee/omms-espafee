from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite
from apps.tenants.models import Tenant

User = get_user_model()


class RootTenantScopingTests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.platform_tenant = Tenant.objects.get(slug="omms-platform")
        self.default_tenant = Tenant.objects.get(slug="vistaai-omms-beta")
        self.alpha = Tenant.objects.create(name="Alpha Outdoor", slug="alpha-root")
        self.beta = Tenant.objects.create(name="Beta Media", slug="beta-root")
        self.platform_admin = User.objects.create_superuser(
            email="platform-root@omms.test",
            username="platform_root",
            password=self.password,
            tenant=self.platform_tenant,
        )
        self.alpha_admin = self._user("alpha-admin@omms.test", "alpha_admin_root", User.Role.ADMIN, self.alpha)
        self.beta_admin = self._user("beta-admin@omms.test", "beta_admin_root", User.Role.ADMIN, self.beta)
        self.alpha_client = self._user("alpha-client@omms.test", "alpha_client_root", User.Role.CLIENT, self.alpha)
        self.beta_client = self._user("beta-client@omms.test", "beta_client_root", User.Role.CLIENT, self.beta)
        self.alpha_site = self._site("Alpha Site", "ALPHA-SITE-1", self.alpha_admin, self.alpha)
        self.beta_site = self._site("Beta Site", "BETA-SITE-1", self.beta_admin, self.beta)
        self.alpha_campaign = self._campaign("Alpha Campaign", "ALPHA-CMP-1", self.alpha_client, self.alpha_admin, self.alpha)
        self.beta_campaign = self._campaign("Beta Campaign", "BETA-CMP-1", self.beta_client, self.beta_admin, self.beta)

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
            address="Test Road",
            city="Jammu",
            state="Jammu and Kashmir",
            owner=owner,
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

    def test_existing_root_records_can_be_backfilled_to_default_tenant(self):
        site = self._site("Legacy Site", "LEGACY-SITE-ROOT", self.alpha_admin, self.alpha)
        campaign = self._campaign("Legacy Campaign", "LEGACY-CMP-ROOT", self.alpha_client, self.alpha_admin, self.alpha)
        MediaSite.objects.filter(pk=site.pk).update(tenant=None)
        Campaign.objects.filter(pk=campaign.pk).update(tenant=None)

        import_module("apps.inventory.migrations.0008_backfill_mediasite_tenant").backfill_media_site_tenant(apps, None)
        import_module("apps.campaigns.migrations.0005_backfill_campaign_tenant").backfill_campaign_tenant(apps, None)

        site.refresh_from_db()
        campaign.refresh_from_db()
        self.assertEqual(site.tenant, self.default_tenant)
        self.assertEqual(campaign.tenant, self.alpha)

    def test_creating_media_site_assigns_actor_tenant(self):
        self.client.force_authenticate(user=self.alpha_admin)

        response = self.client.post(
            reverse("inventory-sites-list"),
            {
                "name": "Alpha Created Site",
                "code": "ALPHA-CREATED-SITE",
                "site_type": MediaSite.SiteType.DIGITAL,
                "address": "Created Road",
                "city": "Jammu",
                "state": "Jammu and Kashmir",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = MediaSite.objects.get(pk=response.data["id"])
        self.assertEqual(created.tenant, self.alpha)

    def test_creating_campaign_assigns_actor_tenant(self):
        self.client.force_authenticate(user=self.alpha_admin)

        response = self.client.post(
            reverse("campaigns-list"),
            {
                "name": "Alpha Created Campaign",
                "code": "ALPHA-CREATED-CMP",
                "client": self.alpha_client.id,
                "account_manager": self.alpha_admin.id,
                "start_date": date.today(),
                "end_date": date.today() + timedelta(days=14),
                "budget": "125000.00",
                "status": Campaign.Status.ACTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Campaign.objects.get(pk=response.data["id"])
        self.assertEqual(created.tenant, self.alpha)

    def test_company_admin_cannot_see_other_tenant_inventory_or_campaigns(self):
        self.client.force_authenticate(user=self.alpha_admin)

        sites = self.client.get(reverse("inventory-sites-list"))
        campaigns = self.client.get(reverse("campaigns-list"))
        beta_site_detail = self.client.get(reverse("inventory-sites-detail", args=[self.beta_site.id]))
        beta_campaign_detail = self.client.get(reverse("campaigns-detail", args=[self.beta_campaign.id]))

        self.assertEqual(sites.status_code, status.HTTP_200_OK)
        self.assertEqual(campaigns.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_site.id, {item["id"] for item in sites.data["results"]})
        self.assertNotIn(self.beta_site.id, {item["id"] for item in sites.data["results"]})
        self.assertIn(self.alpha_campaign.id, {item["id"] for item in campaigns.data["results"]})
        self.assertNotIn(self.beta_campaign.id, {item["id"] for item in campaigns.data["results"]})
        self.assertEqual(beta_site_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(beta_campaign_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_platform_admin_can_see_all_root_tenant_records(self):
        self.client.force_authenticate(user=self.platform_admin)

        alpha_site = self.client.get(reverse("inventory-sites-detail", args=[self.alpha_site.id]))
        beta_site = self.client.get(reverse("inventory-sites-detail", args=[self.beta_site.id]))
        alpha_campaign = self.client.get(reverse("campaigns-detail", args=[self.alpha_campaign.id]))
        beta_campaign = self.client.get(reverse("campaigns-detail", args=[self.beta_campaign.id]))

        self.assertEqual(alpha_site.status_code, status.HTTP_200_OK)
        self.assertEqual(beta_site.status_code, status.HTTP_200_OK)
        self.assertEqual(alpha_campaign.status_code, status.HTTP_200_OK)
        self.assertEqual(beta_campaign.status_code, status.HTTP_200_OK)
