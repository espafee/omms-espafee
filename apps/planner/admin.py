from django.contrib import admin

from .models import CampaignProposal, CampaignProposalLine, MediaPlannerShareLink


class CampaignProposalLineInline(admin.TabularInline):
    model = CampaignProposalLine
    extra = 0
    readonly_fields = ("unit_public_id", "availability_snapshot")


@admin.register(MediaPlannerShareLink)
class MediaPlannerShareLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "client", "pricing_mode", "expires_at", "revoked_at", "last_accessed_at")
    list_filter = ("tenant", "pricing_mode", "show_rates", "revoked_at")
    search_fields = ("title", "token_prefix", "client__email")
    readonly_fields = ("token_hash", "token_prefix", "last_accessed_at", "created_at", "updated_at")


@admin.register(CampaignProposal)
class CampaignProposalAdmin(admin.ModelAdmin):
    list_display = ("reference", "campaign_name", "tenant", "status", "selected_unit_count", "availability_conflict_count", "submitted_at")
    list_filter = ("tenant", "status")
    search_fields = ("reference", "campaign_name", "brand_company", "contact_email")
    readonly_fields = ("reference", "submitted_at", "created_at", "updated_at")
    inlines = [CampaignProposalLineInline]
