from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.setup.models import CompanyProfile, OrganizationEmailSettings, SetupAuditLog
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

    def _configure_verified_email_settings(self):
        email_settings, _ = OrganizationEmailSettings.objects.get_or_create(singleton_key=1)
        email_settings.from_email = "mailer@example.com"
        email_settings.reply_to_email = "reply@example.com"
        email_settings.smtp_host = "smtp.example.com"
        email_settings.smtp_port = 587
        email_settings.smtp_username = "mailer"
        email_settings.use_tls = True
        email_settings.use_ssl = False
        email_settings.email_verified = True
        email_settings.set_smtp_password("super-secret-password")
        email_settings.save()
        return email_settings

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

    def test_setup_submit_locks_future_updates(self):
        self._authenticate(self.admin)
        response = self.client.post("/api/v1/setup/submit/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["setup_locked"])
        profile = CompanyProfile.objects.get(singleton_key=1)
        self.assertEqual(profile.setup_status, CompanyProfile.SetupStatus.SUBMITTED)
        self.assertTrue(profile.setup_locked)
        self.assertTrue(SetupAuditLog.objects.filter(action=SetupAuditLog.Action.SUBMITTED).exists())

        update_response = self.client.patch(
            "/api/v1/setup/company-profile/",
            {"company_name": "Blocked"},
            format="json",
        )

        self.assertEqual(update_response.status_code, 403)

    def test_unlock_otp_is_emailed_hashed_and_unlocks_temporarily(self):
        self._authenticate(self.admin)
        self._configure_verified_email_settings()
        self.client.post("/api/v1/setup/submit/", {}, format="json")

        request_response = self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")

        self.assertEqual(request_response.status_code, 200)
        self.assertEqual(request_response.data["status"], "otp_sent")
        self.assertEqual(request_response.data["recipient_email"], "a***n@example.com")
        self.assertEqual(len(mail.outbox), 1)
        otp = mail.outbox[0].body.split("OTP: ")[1].split("\n")[0].strip()
        self.assertRegex(otp, r"^\d{6}$")
        profile = CompanyProfile.objects.get(singleton_key=1)
        self.assertNotEqual(profile.setup_unlock_otp_hash, otp)
        self.assertTrue(profile.setup_unlock_otp_hash)

        verify_response = self.client.post("/api/v1/setup/unlock/verify-otp/", {"otp": otp}, format="json")

        self.assertEqual(verify_response.status_code, 200)
        self.assertFalse(verify_response.data["setup_locked"])
        profile.refresh_from_db()
        self.assertFalse(profile.setup_locked)
        self.assertGreater(profile.setup_unlocked_until, timezone.now())
        self.assertEqual(profile.setup_unlock_otp_hash, "")
        self.assertTrue(SetupAuditLog.objects.filter(action=SetupAuditLog.Action.UNLOCKED).exists())

        update_response = self.client.patch(
            "/api/v1/setup/company-profile/",
            {"company_name": "Unlocked"},
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.data["company_name"], "Unlocked")

    def test_unlock_otp_rejects_after_three_failed_attempts(self):
        self._authenticate(self.admin)
        self._configure_verified_email_settings()
        self.client.post("/api/v1/setup/submit/", {}, format="json")
        self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")

        for _ in range(3):
            response = self.client.post("/api/v1/setup/unlock/verify-otp/", {"otp": "000000"}, format="json")
            self.assertEqual(response.status_code, 400)

        response = self.client.post("/api/v1/setup/unlock/verify-otp/", {"otp": "111111"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many failed attempts", str(response.data))

    def test_manual_lock_relocks_unlocked_setup(self):
        self._authenticate(self.admin)
        self._configure_verified_email_settings()
        self.client.post("/api/v1/setup/submit/", {}, format="json")
        self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")
        otp = mail.outbox[0].body.split("OTP: ")[1].split("\n")[0].strip()
        self.client.post("/api/v1/setup/unlock/verify-otp/", {"otp": otp}, format="json")

        response = self.client.post("/api/v1/setup/lock/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["setup_locked"])
        self.assertTrue(SetupAuditLog.objects.filter(action=SetupAuditLog.Action.LOCKED).exists())

    def test_unlock_otp_request_requires_locked_setup(self):
        self._authenticate(self.admin)
        self._configure_verified_email_settings()

        response = self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unable to send unlock OTP.")
        self.assertEqual(response.data["error"], "Setup is not locked.")
        self.assertEqual(len(mail.outbox), 0)

    def test_unlock_otp_request_requires_super_admin_email(self):
        self.admin.email = ""
        self.admin.save(update_fields=["email"])
        self._authenticate(self.admin)
        self._configure_verified_email_settings()
        self.client.post("/api/v1/setup/submit/", {}, format="json")

        response = self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unable to send unlock OTP.")
        self.assertEqual(response.data["error"], "Super admin email is missing.")
        self.assertEqual(len(mail.outbox), 0)

    def test_unlock_otp_request_requires_verified_smtp_settings(self):
        self._authenticate(self.admin)
        OrganizationEmailSettings.objects.create(
            from_email="mailer@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="mailer",
            use_tls=True,
            use_ssl=False,
            email_verified=False,
        )
        self.client.post("/api/v1/setup/submit/", {}, format="json")

        response = self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unable to send unlock OTP.")
        self.assertEqual(response.data["error"], "SMTP test has not been verified.")
        self.assertEqual(len(mail.outbox), 0)

    def test_unlock_otp_email_failure_returns_safe_error_and_does_not_store_otp(self):
        self._authenticate(self.admin)
        self._configure_verified_email_settings()
        self.client.post("/api/v1/setup/submit/", {}, format="json")

        with patch("apps.setup.services.EmailMessage.send", side_effect=Exception("smtp exploded")):
            response = self.client.post("/api/v1/setup/unlock/request-otp/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unable to send unlock OTP.")
        self.assertEqual(response.data["error"], "Email delivery failed.")
        profile = CompanyProfile.objects.get(singleton_key=1)
        self.assertEqual(profile.setup_unlock_otp_hash, "")
        self.assertTrue(SetupAuditLog.objects.filter(action=SetupAuditLog.Action.OTP_FAILED).exists())
