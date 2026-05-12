from django.contrib import admin

from .models import EmailNotificationLog, Notification, NotificationPreference


@admin.register(EmailNotificationLog)
class EmailNotificationLogAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "recipient_email", "status", "campaign", "booking", "poe_media", "sent_at")
    list_filter = ("notification_type", "status")
    search_fields = ("recipient_email", "recipient_name", "subject", "event_key")
    readonly_fields = ("created_at", "updated_at", "sent_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "title", "event_type", "severity", "recipient", "recipient_role", "is_read")
    list_filter = ("event_type", "severity", "is_read", "delivery_status")
    search_fields = ("title", "message", "recipient__email", "recipient_role")
    readonly_fields = ("created_at", "updated_at", "read_at")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "in_app_enabled", "email_enabled")
    list_filter = ("notification_type", "in_app_enabled", "email_enabled")
    search_fields = ("user__email",)
