from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "role",
        "is_active",
        "is_staff",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name", "organization_name")
    ordering = ("email",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Business Details",
            {
                "fields": (
                    "phone_number",
                    "role",
                    "organization_name",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    readonly_fields = ("created_at", "updated_at")
