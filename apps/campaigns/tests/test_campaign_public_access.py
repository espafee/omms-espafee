from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign, CampaignAccessToken, CampaignAsset
from apps.inventory.models import MediaSite, MediaUnit
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia

User = get_user_model()


class CampaignPublicAccessAPITests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.sales = self._create_user("sales@example.com", "sales_user", User.Role.SALES)
        self.operations = self._create_user("ops@example.com", "ops_user", User.Role.OPERATIONS)
        self.client_user = self._create_user("client@example.com", "client_user", User.Role.CLIENT)

        self.site = MediaSite.objects.create(
            name="Airport Billboard",
            code="SITE-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Airport Road",
            city="Pune",
            state="Maharashtra",
            owner=self.operations,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=True,
            monthly_rate=Decimal("50000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="Summer Visibility Blast",
            code="CMP-ACCESS-001",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            budget=Decimal("250000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Increase commuter visibility",
        )
        self.approved_asset = CampaignAsset.objects.create(
            campaign=self.campaign,
            name="Approved Creative",
            asset_type="image",
            file_url="https://example.com/assets/approved.jpg",
            version="v2",
            is_approved=True,
        )
        self.unapproved_asset = CampaignAsset.objects.create(
            campaign=self.campaign,
            name="Internal Draft",
            asset_type="image",
            file_url="https://example.com/assets/draft.jpg",
            version="v3",
            is_approved=False,
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            booked_rate=Decimal("55000.00"),
            status=Booking.Status.CONFIRMED,
            remarks="Internal scheduling note",
        )
        self.poe_record = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
            verification_score=Decimal("92.00"),
            verification_notes="Matched expected site coordinates",
            checked_by=self.operations,
        )
        self.poe_media = ProofOfExecutionMedia.objects.create(
            poe_record=self.poe_record,
            media_url="https://example.com/poe/evidence.jpg",
            media_type="image",
            captured_at=timezone.now(),
        )

    def _create_user(self, email, username, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
        )

    def test_public_campaign_link_returns_safe_read_only_payload(self):
        access_token, raw_token = CampaignAccessToken.create_with_token(campaign=self.campaign, created_by=self.admin)

        response = self.client.get(reverse("campaigns-public-detail", args=[raw_token]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["link_status"], "active")
        self.assertEqual(response.data["campaign"]["code"], self.campaign.code)
        self.assertEqual(response.data["campaign"]["bookings"][0]["media_unit"]["facing_direction"], "")
        self.assertEqual(len(response.data["campaign"]["assets"]), 1)
        self.assertEqual(response.data["campaign"]["assets"][0]["name"], self.approved_asset.name)
        self.assertNotIn("budget", response.data["campaign"])
        self.assertNotIn("client", response.data["campaign"])
        self.assertNotIn("account_manager", response.data["campaign"])
        self.assertNotIn("booked_rate", response.data["campaign"]["bookings"][0])
        self.assertNotIn("remarks", response.data["campaign"]["bookings"][0])
        self.assertNotIn("latitude", response.data["campaign"]["bookings"][0]["poe_records"][0])
        self.assertNotIn("checked_by", response.data["campaign"]["bookings"][0]["poe_records"][0])
        access_token.refresh_from_db()
        self.assertIsNotNone(access_token.last_accessed_at)

    def test_invalid_public_campaign_link_returns_not_found(self):
        response = self.client.get(reverse("campaigns-public-detail", args=["omms_invalid_token"]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "invalid_token")

    def test_expired_public_campaign_link_returns_gone(self):
        _, raw_token = CampaignAccessToken.create_with_token(
            campaign=self.campaign,
            created_by=self.admin,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.get(reverse("campaigns-public-detail", args=[raw_token]))

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["code"], "expired_token")

    def test_revoked_public_campaign_link_returns_gone(self):
        access_token, raw_token = CampaignAccessToken.create_with_token(campaign=self.campaign, created_by=self.admin)
        access_token.revoke(actor=self.admin)

        response = self.client.get(reverse("campaigns-public-detail", args=[raw_token]))

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["code"], "revoked_token")

    def test_campaign_end_auto_disables_public_campaign_link(self):
        self.campaign.end_date = date.today() - timedelta(days=1)
        self.campaign.save(update_fields=["end_date", "updated_at"])
        _, raw_token = CampaignAccessToken.create_with_token(campaign=self.campaign, created_by=self.admin)

        response = self.client.get(reverse("campaigns-public-detail", args=[raw_token]))

        self.assertEqual(response.status_code, status.HTTP_410_GONE)
        self.assertEqual(response.data["code"], "campaign_ended")

    def test_admin_can_issue_and_revoke_access_token(self):
        self.client.force_authenticate(user=self.admin)

        create_response = self.client.post(
            reverse("campaign-access-links-list"),
            {
                "campaign": self.campaign.id,
                "expires_at": (timezone.now() + timedelta(days=2)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data["token"].startswith("omms_"))
        self.assertEqual(create_response.data["public_path"], f"/campaigns/public/{create_response.data['token']}")

        revoke_response = self.client.post(
            reverse("campaign-access-links-revoke", args=[create_response.data["id"]]),
            format="json",
        )

        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)
        self.assertFalse(revoke_response.data["is_active"])
        self.assertIsNotNone(revoke_response.data["revoked_at"])

    def test_admin_can_list_existing_access_token_with_public_path(self):
        access_token, raw_token = CampaignAccessToken.create_with_token(campaign=self.campaign, created_by=self.admin)
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse("campaign-access-links-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["id"], access_token.id)
        self.assertEqual(response.data["results"][0]["public_path"], f"/campaigns/public/{raw_token}")

    def test_create_reuses_existing_active_token_for_campaign(self):
        access_token, raw_token = CampaignAccessToken.create_with_token(campaign=self.campaign, created_by=self.admin)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("campaign-access-links-list"),
            {"campaign": self.campaign.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], access_token.id)
        self.assertEqual(response.data["token"], raw_token)
        self.assertEqual(response.data["public_path"], f"/campaigns/public/{raw_token}")
        self.assertEqual(CampaignAccessToken.objects.filter(campaign=self.campaign, is_active=True).count(), 1)
