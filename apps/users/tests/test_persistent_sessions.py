from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import AuthRefreshSession

User = get_user_model()


@override_settings(
    ACCESS_TOKEN_LIFETIME_MINUTES=20,
    SESSION_INACTIVITY_TIMEOUT_HOURS=72,
    REFRESH_COOKIE_MAX_AGE_SECONDS=259200,
    AUTH_REFRESH_COOKIE_NAME="omms_refresh_session",
    AUTH_REFRESH_COOKIE_SECURE=True,
    AUTH_REFRESH_COOKIE_SAMESITE="None",
)
class PersistentSessionAPITests(APITestCase):
    def setUp(self):
        self.password = "SecureSession123!"
        self.user = User.objects.create_user(
            email="session-user@example.com",
            username="session_user",
            password=self.password,
            role=User.Role.ADMIN,
        )

    def login(self):
        return self.client.post(
            reverse("auth-login"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )

    def test_login_uses_username_and_does_not_require_email_payload(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)
        self.assertEqual(response.data["user"]["username"], self.user.username)

    def test_login_rejects_email_only_payload(self):
        response = self.client.post(
            reverse("auth-login"),
            {"email": self.user.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_invalid_username_or_password_is_rejected(self):
        invalid_username = self.client.post(
            reverse("auth-login"),
            {"username": "missing_user", "password": self.password},
            format="json",
        )
        invalid_password = self.client.post(
            reverse("auth-login"),
            {"username": self.user.username, "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(invalid_username.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(invalid_password.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_field_staff_can_login_with_username(self):
        field_staff = User.objects.create_user(
            email="field-session@example.com",
            username="field_session",
            password=self.password,
            role=User.Role.FIELD_STAFF,
        )

        response = self.client.post(
            reverse("auth-login"),
            {"username": field_staff.username, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"], User.Role.FIELD_STAFF)

    def test_demo_admin_and_user_accounts_can_login_with_username(self):
        demo_password = "Espa@123"
        admin = User.objects.create_user(
            email="demo-admin@example.com",
            username="admin",
            password=demo_password,
            role=User.Role.ADMIN,
        )
        field_user = User.objects.create_user(
            email="demo-user1@example.com",
            username="user1",
            password=demo_password,
            role=User.Role.FIELD_STAFF,
        )

        for user in (admin, field_user):
            with self.subTest(username=user.username):
                response = self.client.post(
                    reverse("auth-login"),
                    {"username": user.username, "password": demo_password},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["user"]["username"], user.username)

    def test_login_creates_http_only_refresh_session_cookie(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(response.data["user"]["id"], self.user.id)
        self.assertEqual(AuthRefreshSession.objects.filter(user=self.user, revoked_at__isnull=True).count(), 1)
        cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "None")
        self.assertEqual(int(cookie["max-age"]), 259200)
        self.assertEqual(cookie["path"], "/")

    def test_valid_refresh_issues_access_token_and_updates_activity(self):
        self.login()
        session = AuthRefreshSession.objects.get(user=self.user)
        stale_activity = timezone.now() - timedelta(hours=12)
        AuthRefreshSession.objects.filter(id=session.id).update(last_activity_at=stale_activity)

        response = self.client.post(reverse("token-refresh"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        session.refresh_from_db()
        self.assertGreater(session.last_activity_at, stale_activity)
        self.assertIn(settings.AUTH_REFRESH_COOKIE_NAME, response.cookies)

    def test_active_session_remains_valid_beyond_72_total_hours(self):
        self.login()
        session = AuthRefreshSession.objects.get(user=self.user)
        AuthRefreshSession.objects.filter(id=session.id).update(
            created_at=timezone.now() - timedelta(days=10),
            last_activity_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.post(reverse("token-refresh"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_session_expires_after_72_consecutive_inactive_hours(self):
        self.login()
        session = AuthRefreshSession.objects.get(user=self.user)
        AuthRefreshSession.objects.filter(id=session.id).update(last_activity_at=timezone.now() - timedelta(hours=73))

        response = self.client.post(reverse("token-refresh"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "session_expired")
        self.assertEqual(response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]["max-age"], 0)

    def test_logout_revokes_current_refresh_session(self):
        self.login()
        session = AuthRefreshSession.objects.get(user=self.user)

        response = self.client.post(reverse("auth-logout"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)
        refresh_response = self.client.post(reverse("token-refresh"), {}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_revoked_refresh_session_cannot_be_reused(self):
        self.login()
        session = AuthRefreshSession.objects.get(user=self.user)
        session.revoke()

        response = self.client.post(reverse("token-refresh"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_disabled_user_cannot_refresh(self):
        self.login()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(reverse("token-refresh"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_request_updates_session_activity_and_preserves_tenant_claims(self):
        login_response = self.login()
        session = AuthRefreshSession.objects.get(user=self.user)
        stale_activity = timezone.now() - timedelta(hours=2)
        AuthRefreshSession.objects.filter(id=session.id).update(last_activity_at=stale_activity)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        response = self.client.get(reverse("current-user"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], User.Role.ADMIN)
        session.refresh_from_db()
        self.assertGreater(session.last_activity_at, stale_activity)
