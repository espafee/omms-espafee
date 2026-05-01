from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel


class User(TimeStampedModel, AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SALES = "sales", "Sales"
        OPERATIONS = "operations", "Operations"
        FIELD_STAFF = "field_staff", "Field Staff"
        FINANCE = "finance", "Finance"
        CLIENT = "client", "Client"

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    organization_name = models.CharField(max_length=255, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.email
