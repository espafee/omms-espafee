from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .models import CampaignAccessToken


@shared_task(name="apps.campaigns.tasks.deactivate_expired_campaign_access_tokens")
def deactivate_expired_campaign_access_tokens():
    """Deactivate public campaign links that have expired or whose campaign has ended."""
    now = timezone.now()
    today = timezone.localdate()
    token_queryset = CampaignAccessToken.objects.filter(is_active=True).filter(
        Q(expires_at__isnull=False, expires_at__lte=now) | Q(campaign__end_date__lt=today)
    )
    updated_count = token_queryset.update(is_active=False, revoked_at=now, updated_at=now)
    return {"deactivated_tokens": updated_count, "run_date": str(today)}
