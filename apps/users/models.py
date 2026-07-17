from django.contrib.auth.models import AbstractUser
from django.db import OperationalError, ProgrammingError
from django.db import models

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
