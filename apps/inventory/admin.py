from django.contrib import admin

from .models import MediaSite, MediaSiteImage, MediaUnit, MediaUnitImage, RateCard


class MediaSiteImageInline(admin.TabularInline):
    model = MediaSiteImage
    extra = 0
    fields = ("image", "caption", "is_primary", "uploaded_by", "uploaded_at")
    readonly_fields = ("uploaded_at",)


class MediaUnitImageInline(admin.TabularInline):
    model = MediaUnitImage
    extra = 0
    fields = ("image", "caption", "is_primary", "uploaded_by", "uploaded_at")
    readonly_fields = ("uploaded_at",)


@admin.register(MediaSite)
class MediaSiteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "site_type", "city", "state", "owner")
    list_filter = ("site_type", "city", "state")
    search_fields = ("code", "name", "address", "city", "state")
    inlines = [MediaSiteImageInline]


@admin.register(MediaUnit)
class MediaUnitAdmin(admin.ModelAdmin):
    list_display = ("unit_code", "site", "status", "monthly_rate", "is_illuminated")
    list_filter = ("status", "is_illuminated", "site__city")
    search_fields = ("unit_code", "site__name", "site__code")
    inlines = [MediaUnitImageInline]


@admin.register(RateCard)
class RateCardAdmin(admin.ModelAdmin):
    list_display = ("unit", "start_date", "end_date", "base_rate", "tax_percentage")
    list_filter = ("start_date", "end_date")
    search_fields = ("unit__unit_code",)


@admin.register(MediaSiteImage)
class MediaSiteImageAdmin(admin.ModelAdmin):
    list_display = ("site", "caption", "is_primary", "uploaded_by", "uploaded_at")
    list_filter = ("is_primary", "uploaded_at")
    search_fields = ("site__code", "site__name", "caption")
    readonly_fields = ("uploaded_at",)


@admin.register(MediaUnitImage)
class MediaUnitImageAdmin(admin.ModelAdmin):
    list_display = ("media_unit", "caption", "is_primary", "uploaded_by", "uploaded_at")
    list_filter = ("is_primary", "uploaded_at")
    search_fields = ("media_unit__unit_code", "media_unit__site__name", "caption")
    readonly_fields = ("uploaded_at",)
