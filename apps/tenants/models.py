from django.db import models

from core.models import TimeStampedModel


class Tenant(TimeStampedModel):
    class TenantType(models.TextChoices):
        PLATFORM = "platform", "Platform owner"
        CLIENT = "client", "Client company"

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    tenant_type = models.CharField(max_length=20, choices=TenantType.choices, default=TenantType.CLIENT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    contact_email = models.EmailField(blank=True)
    is_default = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["tenant_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_client_tenant",
            )
        ]

    def __str__(self) -> str:
        return self.name
