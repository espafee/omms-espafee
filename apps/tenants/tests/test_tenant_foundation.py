from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.tenants.models import Tenant
from apps.tenants.services import is_company_admin, is_platform_super_admin

User = get_user_model()


class TenantFoundationTests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.platform_tenant = Tenant.objects.get(slug="omms-platform")
        self.alpha = Tenant.objects.create(name="Alpha Outdoor", slug="alpha-outdoor")
        self.beta = Tenant.objects.create(name="Beta Media", slug="beta-media")
        self.platform_admin = User.objects.create_superuser(
            email="owner@omms.test",
            username="owner",
            password=self.password,
            tenant=self.platform_tenant,
        )
        self.alpha_admin = User.objects.create_user(
            email="admin@alpha.test",
            username="alpha_admin",
            password=self.password,
            role=User.Role.ADMIN,
            tenant=self.alpha,
        )
        self.alpha_client = User.objects.create_user(
            email="client@alpha.test",
            username="alpha_client",
            password=self.password,
            role=User.Role.CLIENT,
            tenant=self.alpha,
            organization_name="Alpha Client",
        )
        self.beta_client = User.objects.create_user(
            email="client@beta.test",
            username="beta_client",
            password=self.password,
            role=User.Role.CLIENT,
            tenant=self.beta,
            organization_name="Beta Client",
        )

    def test_platform_and_company_admin_are_distinguished(self):
        self.assertTrue(is_platform_super_admin(self.platform_admin))
        self.assertFalse(is_company_admin(self.platform_admin))
        self.assertFalse(is_platform_super_admin(self.alpha_admin))
        self.assertTrue(is_company_admin(self.alpha_admin))

    def test_company_admin_client_directory_is_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_admin)

        response = self.client.get(reverse("client-directory"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(self.alpha_client.id, result_ids)
        self.assertNotIn(self.beta_client.id, result_ids)

    def test_platform_admin_user_list_can_see_all_tenants(self):
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(reverse("users-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result_ids = {item["id"] for item in response.data["results"]}
        self.assertIn(self.alpha_client.id, result_ids)
        self.assertIn(self.beta_client.id, result_ids)

    def test_company_admin_cannot_assign_user_to_other_tenant(self):
        self.client.force_authenticate(user=self.alpha_admin)
        payload = {
            "tenant": self.beta.id,
        }

        response = self.client.patch(reverse("users-detail", args=[self.alpha_client.id]), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.alpha_client.refresh_from_db()
        self.assertEqual(self.alpha_client.tenant_id, self.alpha.id)

    def test_auth_response_contains_tenant_claims(self):
        response = self.client.post(
            reverse("token-obtain-pair"),
            {"username": self.alpha_admin.username, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["tenant_slug"], self.alpha.slug)
        self.assertEqual(response.data["user"]["tenant_type"], Tenant.TenantType.CLIENT)
        self.assertTrue(response.data["user"]["is_company_admin"])
