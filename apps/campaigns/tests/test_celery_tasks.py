from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.campaigns.models import Campaign, CampaignAccessToken
from apps.campaigns.tasks import deactivate_expired_campaign_access_tokens

User = get_user_model()


class CampaignCeleryTaskTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-celery@example.com",
            username="admin_celery",
            password="x",
            role=User.Role.ADMIN,
        )
        self.client_user = User.objects.create_user(
            email="client-celery@example.com",
            username="client_celery",
            password="x",
            role=User.Role.CLIENT,
        )

    def _create_campaign(self, *, code, end_date):
        return Campaign.objects.create(
            name=code,
            code=code,
            client=self.client_user,
            account_manager=self.admin,
            start_date=date.today() - timedelta(days=7),
            end_date=end_date,
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
        )

    def test_deactivate_expired_campaign_access_tokens_only_touches_expired_links(self):
        active_campaign = self._create_campaign(code="CMP-CELERY-ACTIVE", end_date=date.today() + timedelta(days=7))
        ended_campaign = self._create_campaign(code="CMP-CELERY-ENDED", end_date=date.today() - timedelta(days=1))
        expired_token, _ = CampaignAccessToken.create_with_token(
            campaign=active_campaign,
            created_by=self.admin,
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        ended_token, _ = CampaignAccessToken.create_with_token(campaign=ended_campaign, created_by=self.admin)
        active_token, _ = CampaignAccessToken.create_with_token(
            campaign=active_campaign,
            created_by=self.admin,
            expires_at=timezone.now() + timedelta(days=1),
        )

        result = deactivate_expired_campaign_access_tokens()

        self.assertEqual(result["deactivated_tokens"], 2)
        expired_token.refresh_from_db()
        ended_token.refresh_from_db()
        active_token.refresh_from_db()
        self.assertFalse(expired_token.is_active)
        self.assertFalse(ended_token.is_active)
        self.assertTrue(active_token.is_active)
