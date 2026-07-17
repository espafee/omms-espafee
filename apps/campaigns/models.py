import hashlib
import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class Campaign(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class EffectiveStatus(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        ONGOING = "ongoing", "Ongoing"
        ENDED = "ended", "Ended"
        PAUSED = "paused", "Paused"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="campaigns",
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="client_campaigns",
        on_delete=models.CASCADE,
    )
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="managed_campaigns",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    objective = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name

    def local_date(self):
        tenant = self.tenant if self.tenant_id else None
        timezone_name = (getattr(tenant, "metadata", None) or {}).get("timezone") or settings.TIME_ZONE
        try:
            tenant_timezone = ZoneInfo(timezone_name)
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            tenant_timezone = timezone.get_default_timezone()
        return timezone.localdate(timezone=tenant_timezone)

    def effective_status_at(self, today=None):
        today = today or self.local_date()
        if self.status == self.Status.CANCELLED:
            return self.EffectiveStatus.CANCELLED
        if self.status == self.Status.PAUSED:
            return self.EffectiveStatus.PAUSED
        if self.start_date > today:
            return self.EffectiveStatus.UPCOMING
        if self.end_date < today:
            return self.EffectiveStatus.ENDED
        return self.EffectiveStatus.ONGOING

    @property
    def effective_status(self):
        return self.effective_status_at()

    @property
    def is_ended(self):
        return self.effective_status == self.EffectiveStatus.ENDED

    @property
    def is_ongoing(self):
        return self.effective_status == self.EffectiveStatus.ONGOING

    @property
    def is_upcoming(self):
        return self.effective_status == self.EffectiveStatus.UPCOMING

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            try:
                from apps.tenants.services import get_default_client_tenant

                self.tenant = getattr(self.client, "tenant", None) or get_default_client_tenant()
            except (OperationalError, ProgrammingError):
                pass
        super().save(*args, **kwargs)


class CampaignAsset(TimeStampedModel):
    campaign = models.ForeignKey(Campaign, related_name="assets", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=50)
    file_url = models.URLField()
    version = models.CharField(max_length=30, default="v1")
    is_approved = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.campaign.code} - {self.name}"


class CampaignAccessToken(TimeStampedModel):
    campaign = models.ForeignKey(Campaign, related_name="access_tokens", on_delete=models.CASCADE)
    token_value = models.CharField(max_length=255, unique=True, editable=False, null=True, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    token_prefix = models.CharField(max_length=16, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_campaign_access_tokens",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="revoked_campaign_access_tokens",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def build_hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def issue_token(cls) -> str:
        return f"omms_{secrets.token_urlsafe(32)}"

    @classmethod
    def create_with_token(cls, *, campaign, created_by=None, expires_at=None):
        raw_token = cls.issue_token()
        instance = cls.objects.create(
            campaign=campaign,
            token_value=raw_token,
            token_hash=cls.build_hash(raw_token),
            token_prefix=raw_token[:12],
            created_by=created_by,
            expires_at=expires_at,
        )
        return instance, raw_token

    @property
    def public_path(self) -> str | None:
        if not self.token_value:
            return None
        return f"/campaigns/public/{self.token_value}"

    def matches(self, raw_token: str) -> bool:
        return self.token_hash == self.build_hash(raw_token)

    def has_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def has_campaign_ended(self) -> bool:
        return self.campaign.is_ended

    def is_revoked(self) -> bool:
        return bool(self.revoked_at or not self.is_active)

    def is_available(self) -> bool:
        return not self.is_revoked() and not self.has_expired() and not self.has_campaign_ended()

    def revoke(self, *, actor=None):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_by = actor
        self.save(update_fields=["is_active", "revoked_at", "revoked_by", "updated_at"])

    def mark_accessed(self):
        self.last_accessed_at = timezone.now()
        self.save(update_fields=["last_accessed_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.campaign.code} access token {self.token_prefix}"
