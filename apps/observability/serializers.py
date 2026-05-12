from rest_framework import serializers

from .models import ApiRequestLog, AuditEvent, ImportExportJob


class ApiRequestLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ApiRequestLog
        fields = "__all__"
        read_only_fields = fields


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    actor_role = serializers.CharField(source="actor.role", read_only=True)

    class Meta:
        model = AuditEvent
        fields = "__all__"
        read_only_fields = fields


class ImportExportJobSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    original_file_url = serializers.SerializerMethodField()
    output_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ImportExportJob
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "company_name",
            "status",
            "output_file",
            "rows_total",
            "rows_success",
            "rows_failed",
            "errors",
            "preview_rows",
            "created_at",
            "updated_at",
        ]

    def get_original_file_url(self, obj):
        return obj.original_file.url if obj.original_file else ""

    def get_output_file_url(self, obj):
        return obj.output_file.url if obj.output_file else ""


class PoeAnalyticsSerializer(serializers.Serializer):
    total_poes = serializers.IntegerField()
    suspicious_count = serializers.IntegerField()
    outside_geofence_count = serializers.IntegerField()
    missing_gps_count = serializers.IntegerField()
    duplicate_replacement_count = serializers.IntegerField()
    pending_review_count = serializers.IntegerField()
    overdue_review_count = serializers.IntegerField()
    trends_by_date = serializers.ListField()
    recent_suspicious = serializers.ListField()


class RoleActivitySerializer(serializers.Serializer):
    total_events = serializers.IntegerField()
    by_role = serializers.ListField()
    by_event_type = serializers.ListField()
