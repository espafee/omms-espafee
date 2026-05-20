from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tenant_type", "status", "is_default", "contact_email", "created_at")
    list_filter = ("tenant_type", "status", "is_default")
    search_fields = ("name", "slug", "contact_email")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
