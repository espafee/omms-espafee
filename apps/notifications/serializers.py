from rest_framework import serializers

from .models import EmailNotificationLog, Notification, NotificationPreference


class EmailNotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailNotificationLog
        fields = "__all__"


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["id", "user", "notification_type", "email_enabled", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    recipient_email = serializers.EmailField(source="recipient.email", read_only=True)

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = [
            "id",
            "recipient",
            "recipient_email",
            "recipient_role",
            "company_name",
            "event_type",
            "title",
            "message",
            "severity",
            "delivery_status",
            "retry_count",
            "metadata",
            "read_at",
            "created_at",
            "updated_at",
        ]
