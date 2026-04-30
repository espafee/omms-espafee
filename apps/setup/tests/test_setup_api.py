from __future__ import annotations

from io import BytesIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.setup.models import CompanyProfile, OrganizationEmailSettings
from apps.users.models import User


@override_settings(
    OMMS_ENCRYPTION_KEY="setup-encryption-secret",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@omms.test",
)
class SetupApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", username="admin", password="secret", role=User.Role.ADMIN)
        self.sales = User.objects.create_user(email="sales@example.com", username="sales", password="secret", role=User.Role.SALES)
        self.client = APIClient()

    def _authenticate(self, user):
        self.client.force_authenticate(user=user)

    def _build_logo(self):
        buffer = BytesIO()
        image = Image.new("RGB", (40, 40), color="navy")
        image.save(buffer, format="PNG")
        return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")

    def test_admin_can_fetch_default_company_profile_with_omms_fallback(self):
        self._authenticate(self.admin)
        response = self.client.get("/api/v1/setup/company-profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["branding_name"], "OMMS")
        self.assertTrue(CompanyProfile.objects.filter(singleton_key=1).exists())

    def test_non_admin_cannot_access_setup_endpoints(self):
        self._authenticate(self.sales)
        response = self.client.get("/api/v1/setup/company-profile/")

        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_company_profile(self):
        self._authenticate(self.admin)
        response = self.client.patch(
            "/api/v1/setup/company-profile/",
            {
                "company_name": "OMMS North",
                "legal_name": "Outdoor Media Management Services Private Limited",
                "communication_email": "hello@example.com",
                "invoice_prefix": "INV",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        profile = CompanyProfile.objects.get(singleton_key=1)
        self.assertEqual(profile.company_name, "OMMS North")
        self.assertEqual(response.data["branding_name"], "OMMS North")

    def test_company_profile_supports_logo_upload(self):
        self._authenticate(self.admin)
        response = self.client.patch(
            "/api/v1/setup/company-profile/",
            {
                "company_name": "OMMS Visual",
                "logo": self._build_logo(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["logo_url"])

    def test_smtp_password_is_encrypted_and_not_returned(self):
        self._authenticate(self.admin)
        response = self.client.patch(
            "/api/v1/setup/email-settings/",
            {
                "from_email": "mailer@example.com",
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_username": "mailer",
                "smtp_password": "super-secret-password",
                "use_tls": True,
                "use_ssl": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("smtp_password", response.data)
        settings_obj = OrganizationEmailSettings.objects.get(singleton_key=1)
        self.assertNotEqual(settings_obj.smtp_password_encrypted, "super-secret-password")
        self.assertEqual(settings_obj.get_smtp_password(), "super-secret-password")
        self.assertTrue(response.data["has_smtp_password"])

    def test_test_email_endpoint_marks_settings_verified(self):
        self._authenticate(self.admin)
        self.client.patch(
            "/api/v1/setup/company-profile/",
            {
                "company_name": "OMMS Visual",
                "communication_email": "ops@example.com",
            },
            format="json",
        )
        self.client.patch(
            "/api/v1/setup/email-settings/",
            {
                "from_email": "mailer@example.com",
                "reply_to_email": "reply@example.com",
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_username": "mailer",
                "smtp_password": "super-secret-password",
                "use_tls": True,
                "use_ssl": False,
            },
            format="json",
        )

        response = self.client.post("/api/v1/setup/email-settings/test/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])
        self.assertTrue(OrganizationEmailSettings.objects.get(singleton_key=1).email_verified)

    def test_email_verification_resets_after_settings_change(self):
        email_settings = OrganizationEmailSettings.objects.create(
            from_email="mailer@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="mailer",
            use_tls=True,
            use_ssl=False,
            email_verified=True,
        )
        email_settings.set_smtp_password("super-secret-password")
        email_settings.save()

        self._authenticate(self.admin)
        response = self.client.patch(
            "/api/v1/setup/email-settings/",
            {
                "smtp_host": "smtp-2.example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["email_verified"])
