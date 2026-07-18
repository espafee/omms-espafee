from datetime import timedelta
import uuid

from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class User(TimeStampedModel, AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Company Admin"
        SALES = "sales", "Sales"
        OPERATIONS = "operations", "Operations Manager"
        FIELD_STAFF = "field_staff", "Field Staff"
        POE_REVIEWER = "poe_reviewer", "POE Reviewer"
        FINANCE = "finance", "Finance"
        INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"
        CLIENT = "client", "Client Viewer"

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    organization_name = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=120, blank=True)
    reports_to = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="direct_reports",
    )
    setup_sent_at = models.DateTimeField(blank=True, null=True)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="users",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            try:
                from apps.tenants.services import get_default_client_tenant, get_platform_tenant

                tenant = get_platform_tenant() if self.is_superuser else get_default_client_tenant()
                if tenant is not None:
                    self.tenant = tenant
            except (OperationalError, ProgrammingError):
                pass
        super().save(*args, **kwargs)

    @property
    def is_platform_admin(self) -> bool:
        tenant = getattr(self, "tenant", None)
        return bool(self.is_superuser and tenant and tenant.tenant_type == "platform")

    @property
    def is_company_admin(self) -> bool:
        tenant = getattr(self, "tenant", None)
        return bool(self.role == self.Role.ADMIN and tenant and tenant.tenant_type == "client")


class AuthRefreshSession(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auth_refresh_sessions",
    )
    token_hash = models.CharField(max_length=128, unique=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)
    revoked_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ("-last_activity_at", "-created_at")
        indexes = [
            models.Index(fields=("user", "revoked_at")),
            models.Index(fields=("last_activity_at",)),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.id}"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def expires_at(self):
        return self.last_activity_at + timedelta(hours=settings.SESSION_INACTIVITY_TIMEOUT_HOURS)

    def is_expired(self, at_time=None) -> bool:
        current_time = at_time or timezone.now()
        return self.expires_at() <= current_time

    def is_active_session(self, at_time=None) -> bool:
        return not self.is_revoked and not self.is_expired(at_time) and self.user.is_active

    def touch(self, at_time=None):
        current_time = at_time or timezone.now()
        self.last_activity_at = current_time
        self.save(update_fields=["last_activity_at", "updated_at"])

    def revoke(self, at_time=None):
        if self.revoked_at:
            return
        self.revoked_at = at_time or timezone.now()
        self.save(update_fields=["revoked_at", "updated_at"])
