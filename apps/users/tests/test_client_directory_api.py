from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class ClientDirectoryAPITests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.sales = self._create_user("sales@example.com", "sales_user", User.Role.SALES)
        self.operations = self._create_user("ops@example.com", "ops_user", User.Role.OPERATIONS)
        self.client_user = self._create_user(
            "client@example.com",
            "client_user",
            User.Role.CLIENT,
            organization_name="Skyline Ads",
        )

    def _create_user(self, email, username, role, is_staff=False, organization_name=""):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
            organization_name=organization_name,
        )

    def test_admin_can_list_client_directory(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("client-directory"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.client_user.id)
        self.assertNotIn("role", response.data["results"][0])

    def test_sales_can_list_client_directory(self):
        self.client.force_authenticate(user=self.sales)

        response = self.client.get(reverse("client-directory"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_non_backoffice_user_cannot_list_client_directory(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.get(reverse("client-directory"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_client_user(self):
        self.client.force_authenticate(user=self.admin)
        payload = {
            "email": "new-client@example.com",
            "username": "new_client",
            "first_name": "Nadia",
            "last_name": "Shah",
            "phone_number": "9999999999",
            "organization_name": "North Reach Media",
            "password": "NewClient123!",
            "is_active": True,
        }

        response = self.client.post(reverse("client-directory"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email=payload["email"])
        self.assertEqual(created_user.role, User.Role.CLIENT)
        self.assertTrue(created_user.check_password(payload["password"]))
        self.assertEqual(response.data["organization_name"], payload["organization_name"])
        self.assertNotIn("password", response.data)

    def test_sales_cannot_create_client_user(self):
        self.client.force_authenticate(user=self.sales)
        payload = {
            "email": "blocked-client@example.com",
            "username": "blocked_client",
            "organization_name": "Blocked Org",
            "password": "Blocked123!",
        }

        response = self.client.post(reverse("client-directory"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())
