from django.contrib import admin

from .models import EmailNotificationLog


@admin.register(EmailNotificationLog)
class EmailNotificationLogAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "recipient_email", "status", "campaign", "booking", "poe_media", "sent_at")
    list_filter = ("notification_type", "status")
    search_fields = ("recipient_email", "recipient_name", "subject", "event_key")
    readonly_fields = ("created_at", "updated_at", "sent_at")
