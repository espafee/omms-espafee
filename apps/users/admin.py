from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AuthRefreshSession, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "role",
        "tenant",
        "is_active",
        "is_staff",
    )
    list_filter = ("role", "tenant", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "username", "first_name", "last_name", "organization_name", "region")
    ordering = ("email",)
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Business Details",
            {
                "fields": (
                    "phone_number",
                    "role",
                    "organization_name",
                    "region",
                    "reports_to",
                    "tenant",
                    "setup_sent_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    readonly_fields = ("setup_sent_at", "created_at", "updated_at")


@admin.register(AuthRefreshSession)
class AuthRefreshSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "last_activity_at", "revoked_at", "created_at")
    list_filter = ("revoked_at", "created_at", "last_activity_at")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("id", "user", "token_hash", "user_agent", "ip_address", "created_at", "updated_at")
