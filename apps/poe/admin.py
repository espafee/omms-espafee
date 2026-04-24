from django.contrib import admin

from .models import ProofOfExecution, ProofOfExecutionMedia, ProofOfExecutionVerificationLog


@admin.register(ProofOfExecution)
class ProofOfExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "booking",
        "executed_on",
        "captured_at",
        "checked_by",
        "verification_status",
        "verification_score",
    )
    list_filter = ("verification_status", "executed_on", "captured_at")
    search_fields = ("booking__campaign__code", "booking__media_unit__unit_code")


@admin.register(ProofOfExecutionMedia)
class ProofOfExecutionMediaAdmin(admin.ModelAdmin):
    list_display = ("poe_record", "media_type", "captured_at", "captured_by")
    list_filter = ("media_type",)
    search_fields = ("media_url", "note")


@admin.register(ProofOfExecutionVerificationLog)
class ProofOfExecutionVerificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "poe_record",
        "verified_by",
        "status_before",
        "status_after",
        "verification_score",
        "distance_meters",
        "created_at",
    )
    list_filter = ("status_after", "created_at")
    search_fields = ("poe_record__booking__campaign__code", "poe_record__booking__media_unit__unit_code", "notes")
