from rest_framework import serializers

from .models import EmailNotificationLog, NotificationPreference


class EmailNotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailNotificationLog
        fields = "__all__"


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["id", "user", "notification_type", "email_enabled", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
