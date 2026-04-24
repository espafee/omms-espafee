from django.contrib import admin
from django.utils import timezone

from .models import Campaign, CampaignAccessToken, CampaignAsset


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "client", "account_manager", "status", "start_date", "end_date")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("code", "name", "client__email", "account_manager__email")


@admin.register(CampaignAsset)
class CampaignAssetAdmin(admin.ModelAdmin):
    list_display = ("campaign", "name", "asset_type", "version", "is_approved")
    list_filter = ("asset_type", "is_approved")
    search_fields = ("name", "campaign__name", "campaign__code")


@admin.register(CampaignAccessToken)
class CampaignAccessTokenAdmin(admin.ModelAdmin):
    list_display = (
        "token_prefix",
        "campaign",
        "is_active",
        "expires_at",
        "revoked_at",
        "created_by",
        "last_accessed_at",
    )
    list_filter = ("is_active", "expires_at", "revoked_at", "created_at")
    search_fields = ("token_prefix", "campaign__name", "campaign__code")
    readonly_fields = ("token_hash", "token_prefix", "last_accessed_at", "created_at", "updated_at")
    actions = ("revoke_selected_tokens",)

    @admin.action(description="Revoke selected campaign access tokens")
    def revoke_selected_tokens(self, request, queryset):
        for token in queryset.filter(revoked_at__isnull=True, is_active=True):
            token.is_active = False
            token.revoked_at = timezone.now()
            token.revoked_by = request.user
            token.save(update_fields=["is_active", "revoked_at", "revoked_by", "updated_at"])
