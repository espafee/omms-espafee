from django.contrib import admin

from .models import Issue


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("booking", "issue_type", "priority", "status", "reporter_type", "reported_by", "created_at")
    list_filter = ("status", "priority", "issue_type", "reporter_type", "created_at")
    search_fields = (
        "description",
        "booking__campaign__name",
        "booking__media_unit__unit_code",
        "booking__media_unit__site__name",
        "reported_by__email",
    )
