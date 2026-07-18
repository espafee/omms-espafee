from __future__ import annotations

import hashlib
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


def proposal_reference():
    return f"PRP-{uuid.uuid4().hex[:10].upper()}"


class MediaPlannerShareLink(TimeStampedModel):
    class PricingMode(models.TextChoices):
        HIDDEN = "hidden", "Hidden"
        STANDARD_SELLING_RATE = "standard_selling_rate", "Standard selling rate"
        CLIENT_RATE_CARD = "client_rate_card", "Client rate card"

    tenant = models.ForeignKey("tenants.Tenant", related_name="media_planner_links", on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    token_prefix = models.CharField(max_length=16, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_media_planner_links",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="media_planner_links",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, default="Live Media Planner")
    allowed_cities = models.JSONField(default=list, blank=True)
    allowed_regions = models.JSONField(default=list, blank=True)
    allowed_inventory_types = models.JSONField(default=list, blank=True)
    show_rates = models.BooleanField(default=False)
    pricing_mode = models.CharField(max_length=30, choices=PricingMode.choices, default=PricingMode.HIDDEN)
    allow_proposal_submission = models.BooleanField(default=True)
    allow_image_download = models.BooleanField(default=False)
    allow_map_data = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["tenant", "revoked_at", "expires_at"])]

    @staticmethod
    def build_hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def issue_token(cls) -> str:
        return f"planner_{secrets.token_urlsafe(32)}"

    @classmethod
    def create_with_token(cls, **values):
        raw_token = cls.issue_token()
        instance = cls.objects.create(
            token_hash=cls.build_hash(raw_token),
            token_prefix=raw_token[:16],
            **values,
        )
        return instance, raw_token

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_revoked(self):
        return bool(self.revoked_at)

    @property
    def is_available(self):
        return not self.is_revoked and not self.is_expired

    @property
    def effective_show_rates(self):
        return bool(self.show_rates and self.pricing_mode == self.PricingMode.STANDARD_SELLING_RATE)

    def __str__(self):
        return f"{self.tenant} / {self.title} / {self.token_prefix}"


class CampaignProposal(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        AVAILABILITY_CONFIRMED = "availability_confirmed", "Availability confirmed"
        ESTIMATE_PREPARED = "estimate_prepared", "Estimate prepared"
        SENT_TO_CLIENT = "sent_to_client", "Sent to client"
        CLIENT_APPROVED = "client_approved", "Client approved"
        CLIENT_REJECTED = "client_rejected", "Client rejected"
        CONVERTED_TO_CAMPAIGN = "converted_to_campaign", "Converted to campaign"
        EXPIRED = "expired", "Expired"

    tenant = models.ForeignKey("tenants.Tenant", related_name="campaign_proposals", on_delete=models.PROTECT)
    share_link = models.ForeignKey(MediaPlannerShareLink, related_name="proposals", on_delete=models.PROTECT)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="media_planner_proposals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reference = models.CharField(max_length=20, unique=True, default=proposal_reference, editable=False)
    campaign_name = models.CharField(max_length=255)
    brand_company = models.CharField(max_length=255, blank=True)
    objective = models.TextField(blank=True)
    requested_start_date = models.DateField()
    requested_end_date = models.DateField()
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30, blank=True)
    billing_gstin = models.CharField(max_length=15, blank=True)
    billing_details = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=40, default="live_media_planner")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reviewed_campaign_proposals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_campaign_proposals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    preliminary_subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    selected_unit_count = models.PositiveIntegerField(default=0)
    availability_conflict_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=64, blank=True)
    estimate = models.OneToOneField(
        "billing.CampaignEstimate",
        related_name="planner_proposal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    converted_campaign = models.OneToOneField(
        "campaigns.Campaign",
        related_name="source_proposal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-submitted_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status", "submitted_at"]),
            models.Index(fields=["share_link", "idempotency_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["share_link", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="unique_planner_submission_idempotency",
            )
        ]

    def __str__(self):
        return f"{self.reference} / {self.campaign_name}"


class CampaignProposalLine(TimeStampedModel):
    proposal = models.ForeignKey(CampaignProposal, related_name="lines", on_delete=models.CASCADE)
    media_unit = models.ForeignKey(
        "inventory.MediaUnit",
        related_name="proposal_lines",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    unit_public_id = models.UUIDField()
    unit_code = models.CharField(max_length=50)
    location_name = models.CharField(max_length=255)
    public_address = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)
    width = models.DecimalField(max_digits=8, decimal_places=2)
    height = models.DecimalField(max_digits=8, decimal_places=2)
    facing_direction = models.CharField(max_length=150, blank=True)
    display_format = models.CharField(max_length=40, blank=True)
    is_illuminated = models.BooleanField(default=False)
    monthly_rate_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    availability_status = models.CharField(max_length=30)
    availability_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["proposal", "unit_public_id"], name="unique_unit_per_proposal")]

    def __str__(self):
        return f"{self.proposal.reference} / {self.unit_code}"
