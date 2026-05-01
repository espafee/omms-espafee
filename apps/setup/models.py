from __future__ import annotations

from django.db import models
from django.conf import settings

from core.crypto import decrypt_text, encrypt_text
from core.models import TimeStampedModel


class SingletonModel(TimeStampedModel):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        super().save(*args, **kwargs)


class CompanyProfile(SingletonModel):
    class SetupStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    company_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to="branding/logos/", blank=True, null=True)
    communication_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    state_code = models.CharField(max_length=10, blank=True)
    invoice_prefix = models.CharField(max_length=20, blank=True, default="INV")
    bank_details = models.TextField(blank=True)
    authorised_signatory = models.CharField(max_length=255, blank=True)
    setup_status = models.CharField(max_length=20, choices=SetupStatus.choices, default=SetupStatus.DRAFT)
    setup_locked = models.BooleanField(default=False)
    setup_unlocked_until = models.DateTimeField(blank=True, null=True)
    setup_unlock_requested_at = models.DateTimeField(blank=True, null=True)
    setup_unlock_otp_hash = models.CharField(max_length=255, blank=True)
    setup_unlock_otp_expires_at = models.DateTimeField(blank=True, null=True)
    setup_unlock_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Company profile"
        verbose_name_plural = "Company profile"

    def __str__(self) -> str:
        return self.branding_name

    @property
    def branding_name(self) -> str:
        return self.company_name or self.legal_name or "OMMS"


class SetupAuditLog(TimeStampedModel):
    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Setup submitted"
        OTP_REQUESTED = "otp_requested", "OTP requested"
        OTP_VERIFIED = "otp_verified", "OTP verified"
        OTP_FAILED = "otp_failed", "OTP verification failed"
        UNLOCKED = "unlocked", "Setup unlocked"
        LOCKED = "locked", "Setup locked"

    action = models.CharField(max_length=40, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} at {self.created_at:%Y-%m-%d %H:%M}"


class OrganizationEmailSettings(SingletonModel):
    from_email = models.EmailField(blank=True)
    reply_to_email = models.EmailField(blank=True)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password_encrypted = models.TextField(blank=True)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Organization email settings"
        verbose_name_plural = "Organization email settings"

    def __str__(self) -> str:
        return self.from_email or "Organization email settings"

    @property
    def has_smtp_password(self) -> bool:
        return bool(self.smtp_password_encrypted)

    def set_smtp_password(self, raw_password: str) -> None:
        self.smtp_password_encrypted = encrypt_text(raw_password)

    def clear_smtp_password(self) -> None:
        self.smtp_password_encrypted = ""

    def get_smtp_password(self) -> str:
        return decrypt_text(self.smtp_password_encrypted)
