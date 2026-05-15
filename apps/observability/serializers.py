from rest_framework import serializers

from .models import AlertEvent, AlertRule, ApiRequestLog, AuditEvent, ImportExportJob


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
    progress_percent = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()

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
            "rows_updated",
            "rows_skipped",
            "rows_failed",
            "errors",
            "preview_rows",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_original_file_url(self, obj):
        return obj.original_file.url if obj.original_file else ""

    def get_output_file_url(self, obj):
        return obj.output_file.url if obj.output_file else ""

    def get_progress_percent(self, obj):
        if obj.status == ImportExportJob.Status.COMPLETED:
            return 100
        processed = obj.rows_success + obj.rows_updated + obj.rows_skipped + obj.rows_failed
        if not obj.rows_total:
            return 0
        if obj.status in {ImportExportJob.Status.CONFIRMED, ImportExportJob.Status.PROCESSING}:
            return max(1, min(99, round((processed / obj.rows_total) * 100)))
        return 0

    def get_duration_seconds(self, obj):
        if not obj.started_at:
            return None
        end = obj.completed_at or obj.updated_at
        return max(0, int((end - obj.started_at).total_seconds()))


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


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class AlertEventSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = AlertEvent
        fields = "__all__"
        read_only_fields = fields
