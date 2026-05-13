from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class TrainingDocumentAccessTests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.admin = User.objects.create_user(
            email="training-admin@example.com",
            username="training_admin",
            password=self.password,
            role=User.Role.ADMIN,
        )
        self.finance = User.objects.create_user(
            email="training-finance@example.com",
            username="training_finance",
            password=self.password,
            role=User.Role.FINANCE,
        )
        self.client_user = User.objects.create_user(
            email="training-client@example.com",
            username="training_client",
            password=self.password,
            role=User.Role.CLIENT,
        )

    def test_anonymous_users_cannot_list_training_documents(self):
        response = self.client.get(reverse("training-document-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_download_admin_training_document(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(reverse("training-document-download", kwargs={"slug": "admin-super-admin"}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_finance_user_sees_finance_guide_but_not_admin_guide(self):
        self.client.force_authenticate(self.finance)

        list_response = self.client.get(reverse("training-document-list"))
        slugs = {document["slug"] for document in list_response.data}

        self.assertIn("master-manual", slugs)
        self.assertIn("finance-team", slugs)
        self.assertNotIn("admin-super-admin", slugs)

        forbidden_response = self.client.get(
            reverse("training-document-download", kwargs={"slug": "admin-super-admin"})
        )
        allowed_response = self.client.get(reverse("training-document-download", kwargs={"slug": "finance-team"}))

        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed_response.status_code, status.HTTP_200_OK)

    def test_client_can_only_access_general_training_manual(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(reverse("training-document-list"))
        slugs = {document["slug"] for document in response.data}

        self.assertEqual(slugs, {"master-manual"})
