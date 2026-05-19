from django.utils import timezone
from rest_framework import serializers

from .models import AlertEvent, AlertRule, ApiRequestLog, AuditEvent, ImportExportJob, SavedOperationalView


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
    retry_of_id = serializers.IntegerField(source="retry_of.id", read_only=True)
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
            "retry_of",
            "retry_count",
            "last_retry_at",
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


class OperationalSearchResultSerializer(serializers.Serializer):
    module = serializers.CharField()
    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    status = serializers.CharField(allow_blank=True)
    url = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField(allow_null=True)
    metadata = serializers.DictField()


class OperationalSearchSerializer(serializers.Serializer):
    query = serializers.CharField(allow_blank=True)
    total = serializers.IntegerField()
    results = OperationalSearchResultSerializer(many=True)
    grouped = serializers.DictField()


class SavedOperationalViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedOperationalView
        fields = [
            "id",
            "name",
            "view_type",
            "module",
            "search_query",
            "filters",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_filters(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be an object.")
        return value


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
    current_value = serializers.SerializerMethodField()
    last_triggered_at = serializers.SerializerMethodField()
    cooldown_until = serializers.SerializerMethodField()
    cooldown_remaining_minutes = serializers.SerializerMethodField()

    class Meta:
        model = AlertRule
        fields = [
            "id",
            "name",
            "metric",
            "threshold",
            "window_minutes",
            "cooldown_minutes",
            "severity",
            "is_enabled",
            "current_value",
            "last_triggered_at",
            "cooldown_until",
            "cooldown_remaining_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_value", "last_triggered_at", "cooldown_until", "cooldown_remaining_minutes", "created_at", "updated_at"]

    def get_current_value(self, obj):
        from .services import get_alert_metric_value

        return get_alert_metric_value(obj)

    def get_last_triggered_at(self, obj):
        latest_event = obj.events.order_by("-created_at").first()
        return latest_event.created_at if latest_event else None

    def get_cooldown_until(self, obj):
        latest_event = obj.events.order_by("-created_at").first()
        if not latest_event:
            return None
        return latest_event.created_at + timezone.timedelta(minutes=obj.cooldown_minutes)

    def get_cooldown_remaining_minutes(self, obj):
        cooldown_until = self.get_cooldown_until(obj)
        if not cooldown_until:
            return 0
        remaining = cooldown_until - timezone.now()
        return max(0, int(remaining.total_seconds() // 60))


class AlertEventSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    acknowledged_by_email = serializers.EmailField(source="acknowledged_by.email", read_only=True)
    is_acknowledged = serializers.SerializerMethodField()

    class Meta:
        model = AlertEvent
        fields = [
            "id",
            "rule",
            "rule_name",
            "metric",
            "observed_value",
            "threshold",
            "severity",
            "summary",
            "metadata",
            "acknowledged_at",
            "acknowledged_by",
            "acknowledged_by_email",
            "is_acknowledged",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_acknowledged(self, obj):
        return obj.acknowledged_at is not None
