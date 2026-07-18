from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.campaigns.models import Campaign
from apps.observability.models import AuditEvent
from apps.tenants.models import Tenant

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@omms.test",
    FRONTEND_PUBLIC_BASE_URL="https://omms.example.test",
)
class TeamAccessAPITests(APITestCase):
    def setUp(self):
        self.password = "SecureTestPass123!"
        self.platform_tenant = Tenant.objects.get(slug="omms-platform")
        self.alpha = Tenant.objects.create(name="Alpha Outdoor", slug="team-alpha")
        self.beta = Tenant.objects.create(name="Beta Media", slug="team-beta")
        self.platform_admin = User.objects.create_superuser(
            email="platform-team@omms.test",
            username="platform_team",
            password=self.password,
            tenant=self.platform_tenant,
        )
        self.alpha_admin = self._user("admin@alpha-team.test", "alpha_team_admin", User.Role.ADMIN, self.alpha)
        self.alpha_operations = self._user("ops@alpha-team.test", "alpha_team_ops", User.Role.OPERATIONS, self.alpha)
        self.beta_admin = self._user("admin@beta-team.test", "beta_team_admin", User.Role.ADMIN, self.beta)
        self.beta_field = self._user("field@beta-team.test", "beta_team_field", User.Role.FIELD_STAFF, self.beta)

    def _user(self, email, username, role, tenant, *, active=True):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            tenant=tenant,
            is_active=active,
        )

    def _payload(self, **overrides):
        payload = {
            "email": "new-field@alpha-team.test",
            "first_name": "New",
            "last_name": "Field",
            "phone_number": "+91 9000000000",
            "role": User.Role.FIELD_STAFF,
            "region": "Jammu",
            "reports_to": self.alpha_operations.id,
            "send_setup": False,
        }
        payload.update(overrides)
        return payload

    def test_platform_admin_can_create_user_for_selected_tenant(self):
        self.client.force_authenticate(self.platform_admin)

        response = self.client.post(
            reverse("team-users-list"),
            self._payload(email="platform-created@beta.test", tenant=self.beta.id, reports_to=self.beta_admin.id),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="platform-created@beta.test")
        self.assertEqual(created.tenant, self.beta)
        self.assertEqual(created.role, User.Role.FIELD_STAFF)
        self.assertFalse(created.has_usable_password())

    def test_company_admin_creates_user_only_in_own_tenant(self):
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.post(reverse("team-users-list"), self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="new-field@alpha-team.test")
        self.assertEqual(created.tenant, self.alpha)
        self.assertEqual(created.region, "Jammu")
        self.assertEqual(created.reports_to, self.alpha_operations)
        self.assertTrue(AuditEvent.objects.filter(event_type="team.user.created", entity_id=str(created.id)).exists())

    def test_company_admin_cannot_create_or_edit_cross_tenant_user(self):
        self.client.force_authenticate(self.alpha_admin)

        create_response = self.client.post(
            reverse("team-users-list"),
            self._payload(email="wrong-tenant@alpha.test", tenant=self.beta.id, reports_to=None),
            format="json",
        )
        edit_response = self.client.patch(
            reverse("team-users-detail", args=[self.beta_field.id]),
            {"first_name": "Blocked"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(edit_response.status_code, status.HTTP_404_NOT_FOUND)
        self.beta_field.refresh_from_db()
        self.assertNotEqual(self.beta_field.first_name, "Blocked")
        self.assertTrue(AuditEvent.objects.filter(event_type="team.access.denied", actor=self.alpha_admin).exists())

    def test_company_admin_cannot_create_platform_admin_or_unsupported_role(self):
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.post(
            reverse("team-users-list"),
            self._payload(role="platform_admin", email="forbidden-admin@alpha.test"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="forbidden-admin@alpha.test").exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type="team.access.denied",
                actor=self.alpha_admin,
                metadata__reason="unsupported_role",
            ).exists()
        )

    def test_non_admin_cannot_list_or_manage_users(self):
        self.client.force_authenticate(self.alpha_operations)

        list_response = self.client.get(reverse("team-users-list"))
        create_response = self.client.post(reverse("team-users-list"), self._payload(), format="json")

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_legacy_user_api_cannot_bypass_audited_access_controls(self):
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.patch(
            reverse("users-detail", args=[self.alpha_operations.id]),
            {"is_active": False, "role": User.Role.ADMIN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.alpha_operations.refresh_from_db()
        self.assertTrue(self.alpha_operations.is_active)
        self.assertEqual(self.alpha_operations.role, User.Role.OPERATIONS)

    def test_team_listing_is_tenant_isolated_latest_first_and_filterable(self):
        newest = self._user("reviewer@alpha.test", "alpha_reviewer", User.Role.POE_REVIEWER, self.alpha)
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.get(reverse("team-users-list"), {"role": User.Role.POE_REVIEWER})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [newest.id])
        self.assertNotIn(self.beta_field.id, ids)

    def test_roles_endpoint_excludes_platform_admin_and_exposes_specialists(self):
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.get(reverse("team-roles"))

        values = {role["value"] for role in response.data["roles"]}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("platform_admin", values)
        self.assertIn(User.Role.POE_REVIEWER, values)
        self.assertIn(User.Role.INVENTORY_MANAGER, values)
        self.assertFalse(response.data["can_select_tenant"])
        self.assertEqual(response.data["tenants"], [{"id": self.alpha.id, "name": self.alpha.name, "slug": self.alpha.slug}])

    def test_specialist_roles_are_limited_to_relevant_modules(self):
        inventory_manager = self._user(
            "inventory@alpha.test",
            "alpha_inventory_manager",
            User.Role.INVENTORY_MANAGER,
            self.alpha,
        )
        poe_reviewer = self._user("review@alpha.test", "alpha_poe_reviewer", User.Role.POE_REVIEWER, self.alpha)

        self.client.force_authenticate(inventory_manager)
        inventory_response = self.client.get(reverse("inventory-sites-list"))
        inventory_campaign_response = self.client.get(reverse("campaigns-list"))
        inventory_booking_response = self.client.get(reverse("bookings-list"))
        inventory_profile_response = self.client.get(reverse("observability-dashboard-profile"))
        inventory_mode_response = self.client.get(reverse("observability-operational-mode"))
        inventory_billing_response = self.client.get(reverse("billing-invoices-list"))
        self.client.force_authenticate(poe_reviewer)
        poe_response = self.client.get(reverse("poe-list"))
        poe_billing_response = self.client.get(reverse("billing-invoices-list"))

        self.assertEqual(inventory_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inventory_campaign_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inventory_booking_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inventory_profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inventory_mode_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inventory_billing_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(poe_response.status_code, status.HTTP_200_OK)
        self.assertEqual(poe_billing_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivate_blocks_authentication_and_reactivate_restores_it(self):
        target = self._user("active-field@alpha.test", "active_alpha_field", User.Role.FIELD_STAFF, self.alpha)
        self.client.force_authenticate(self.alpha_admin)

        deactivate_response = self.client.post(reverse("team-users-deactivate", args=[target.id]), {}, format="json")
        self.client.force_authenticate(None)
        blocked_login = self.client.post(
            reverse("token-obtain-pair"),
            {"email": target.email, "password": self.password},
            format="json",
        )
        self.client.force_authenticate(self.alpha_admin)
        reactivate_response = self.client.post(reverse("team-users-reactivate", args=[target.id]), {}, format="json")
        self.client.force_authenticate(None)
        restored_login = self.client.post(
            reverse("token-obtain-pair"),
            {"email": target.email, "password": self.password},
            format="json",
        )

        self.assertEqual(deactivate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(blocked_login.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(reactivate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(restored_login.status_code, status.HTTP_200_OK)
        self.assertTrue(AuditEvent.objects.filter(event_type="team.user.access_removed", entity_id=str(target.id)).exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="team.user.access_restored", entity_id=str(target.id)).exists())

    def test_deactivation_retains_history_and_hard_delete_is_blocked(self):
        client_user = self._user("history-client@alpha.test", "history_alpha_client", User.Role.CLIENT, self.alpha)
        campaign = Campaign.objects.create(
            name="History campaign",
            code="TEAM-HISTORY-001",
            tenant=self.alpha,
            client=client_user,
            account_manager=self.alpha_admin,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            budget=Decimal("10000.00"),
            status=Campaign.Status.ACTIVE,
        )
        self.client.force_authenticate(self.alpha_admin)

        deactivate_response = self.client.post(reverse("team-users-deactivate", args=[client_user.id]), {}, format="json")
        delete_response = self.client.delete(reverse("team-users-detail", args=[client_user.id]))

        self.assertEqual(deactivate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(delete_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(User.objects.filter(pk=client_user.id).exists())
        self.assertTrue(Campaign.objects.filter(pk=campaign.id, client=client_user).exists())

    def test_role_change_is_audit_logged(self):
        target = self._user("role-change@alpha.test", "role_change_alpha", User.Role.FIELD_STAFF, self.alpha)
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.patch(
            reverse("team-users-detail", args=[target.id]),
            {"role": User.Role.POE_REVIEWER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.POE_REVIEWER)
        event = AuditEvent.objects.get(event_type="team.user.role_changed", entity_id=str(target.id))
        self.assertEqual(event.metadata["previous_role"], User.Role.FIELD_STAFF)
        self.assertEqual(event.metadata["new_role"], User.Role.POE_REVIEWER)

    def test_legacy_role_user_can_be_edited_without_making_role_assignable(self):
        legacy_sales = self._user("legacy-sales@alpha.test", "legacy_sales_alpha", User.Role.SALES, self.alpha)
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.patch(
            reverse("team-users-detail", args=[legacy_sales.id]),
            {"first_name": "Legacy", "role": User.Role.SALES},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        legacy_sales.refresh_from_db()
        self.assertEqual(legacy_sales.first_name, "Legacy")
        self.assertEqual(legacy_sales.role, User.Role.SALES)

    def test_rejected_role_change_is_audited_without_mutating_user(self):
        target = self._user("blocked-role@alpha.test", "blocked_role_alpha", User.Role.FIELD_STAFF, self.alpha)
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.patch(
            reverse("team-users-detail", args=[target.id]),
            {"role": "platform_admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        target.refresh_from_db()
        self.assertEqual(target.role, User.Role.FIELD_STAFF)
        self.assertTrue(
            AuditEvent.objects.filter(
                event_type="team.access.denied",
                actor=self.alpha_admin,
                entity_id=str(target.id),
                metadata__reason="unsupported_role",
            ).exists()
        )

    def test_duplicate_email_is_rejected_without_partial_user(self):
        self.client.force_authenticate(self.alpha_admin)

        response = self.client.post(
            reverse("team-users-list"),
            self._payload(email=self.alpha_operations.email),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(email=self.alpha_operations.email).count(), 1)

    def test_setup_email_uses_one_time_password_token(self):
        target = User.objects.create_user(
            email="invited@alpha.test",
            username="invited_alpha",
            password=None,
            role=User.Role.FIELD_STAFF,
            tenant=self.alpha,
        )
        self.client.force_authenticate(self.alpha_admin)

        send_response = self.client.post(reverse("team-users-send-setup", args=[target.id]), {}, format="json")
        setup_url = next(line for line in mail.outbox[0].body.splitlines() if line.startswith("https://"))
        query = parse_qs(urlparse(setup_url).query)
        self.client.force_authenticate(None)
        complete_response = self.client.post(
            reverse("team-account-setup-complete"),
            {"uid": query["uid"][0], "token": query["token"][0], "password": "NewSecurePass456!"},
            format="json",
        )
        repeat_response = self.client.post(
            reverse("team-account-setup-complete"),
            {"uid": query["uid"][0], "token": query["token"][0], "password": "AnotherSecurePass789!"},
            format="json",
        )

        self.assertEqual(send_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(repeat_response.status_code, status.HTTP_400_BAD_REQUEST)
        target.refresh_from_db()
        self.assertTrue(target.check_password("NewSecurePass456!"))
        self.assertTrue(AuditEvent.objects.filter(event_type="team.user.setup_sent", entity_id=str(target.id)).exists())
