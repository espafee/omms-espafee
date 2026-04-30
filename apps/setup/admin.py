from django.contrib import admin

from .models import CompanyProfile, OrganizationEmailSettings


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("branding_name", "communication_email", "gstin", "invoice_prefix", "updated_at")


@admin.register(OrganizationEmailSettings)
class OrganizationEmailSettingsAdmin(admin.ModelAdmin):
    list_display = ("from_email", "smtp_host", "smtp_port", "email_verified", "updated_at")
