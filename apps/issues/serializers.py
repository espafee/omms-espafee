from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.bookings.models import Assignment, Booking
from core.images import build_public_media_url
from core.roles import FIELD_STAFF

from .models import Issue, IssueTask
from .services import sync_issue_sla_status

User = get_user_model()


def is_admin_like_user(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", None) in {"admin", "super_admin", "owner"}
        )
    )


class IssueSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    booking_display = serializers.SerializerMethodField()
    reported_by_email = serializers.EmailField(source="reported_by.email", read_only=True)
    assignment_user_email = serializers.EmailField(source="assignment.user.email", read_only=True)

    class Meta:
        model = Issue
        fields = [
            "id",
            "booking",
            "booking_display",
            "assignment",
            "assignment_user_email",
            "reported_by",
            "reported_by_email",
            "reporter_type",
            "issue_type",
            "description",
            "image",
            "image_url",
            "latitude",
            "longitude",
            "captured_at",
            "contact",
            "status",
            "priority",
            "priority_reason",
            "first_response_due_at",
            "resolution_due_at",
            "acknowledged_at",
            "sla_status",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = [
            "id",
            "assignment",
            "reported_by",
            "reported_by_email",
            "image_url",
            "priority_reason",
            "first_response_due_at",
            "resolution_due_at",
            "acknowledged_at",
            "sla_status",
            "created_at",
            "updated_at",
            "resolved_at",
        ]

    def get_image_url(self, obj):
        return build_public_media_url(obj.image, request=self.context.get("request"))

    def to_representation(self, instance):
        sync_issue_sla_status(instance)
        return super().to_representation(instance)

    def get_booking_display(self, obj):
        site = obj.booking.media_unit.site
        return {
            "campaign_name": obj.booking.campaign.name,
            "site_name": site.name,
            "unit_name": obj.booking.media_unit.unit_code,
        }

    def validate_booking(self, booking: Booking):
        request = self.context.get("request")
        user = request.user if request else None
        if is_admin_like_user(user):
            return booking
        if getattr(user, "role", None) == FIELD_STAFF and booking.assignments.filter(
            user=user,
            status__in=[Assignment.Status.PENDING, Assignment.Status.COMPLETED],
        ).exists():
            return booking
        raise serializers.ValidationError("You can report issues only for bookings assigned to you.")

    def validate_reporter_type(self, reporter_type):
        request = self.context.get("request")
        user = request.user if request else None
        if self.context.get("public_report"):
            if reporter_type != Issue.ReporterType.CLIENT:
                raise serializers.ValidationError("Public issue reports must use client reporter type.")
            return reporter_type
        if getattr(user, "role", None) == FIELD_STAFF and reporter_type != Issue.ReporterType.FIELD_STAFF:
            raise serializers.ValidationError("Field staff must report as field_staff.")
        if reporter_type == Issue.ReporterType.CLIENT:
            raise serializers.ValidationError("Client issue reporting is not enabled yet.")
        return reporter_type


class PublicIssueReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Issue
        fields = ["issue_type", "description", "image", "contact"]

    def validate_description(self, value):
        if len(value.strip()) < 8:
            raise serializers.ValidationError("Please describe the issue in at least 8 characters.")
        return value.strip()


class IssueTaskSerializer(serializers.ModelSerializer):
    assigned_to_email = serializers.EmailField(source="assigned_to.email", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    assigned_by_email = serializers.EmailField(source="assigned_by.email", read_only=True)
    issue_display = serializers.SerializerMethodField()

    class Meta:
        model = IssueTask
        fields = [
            "id",
            "issue",
            "issue_display",
            "assigned_to",
            "assigned_to_email",
            "assigned_to_name",
            "assigned_by",
            "assigned_by_email",
            "assigned_at",
            "status",
            "due_at",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "issue",
            "issue_display",
            "assigned_to",
            "assigned_to_email",
            "assigned_to_name",
            "assigned_by",
            "assigned_by_email",
            "assigned_at",
            "due_at",
            "completed_at",
            "notes",
            "created_at",
            "updated_at",
        ]

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.get_full_name() or obj.assigned_to.email

    def get_issue_display(self, obj):
        site = obj.issue.booking.media_unit.site
        return {
            "issue_type": obj.issue.issue_type,
            "issue_status": obj.issue.status,
            "priority": obj.issue.priority,
            "campaign_name": obj.issue.booking.campaign.name,
            "site_name": site.name,
            "unit_name": obj.issue.booking.media_unit.unit_code,
        }

    def validate_status(self, value):
        if value not in {IssueTask.Status.IN_PROGRESS, IssueTask.Status.COMPLETED}:
            raise serializers.ValidationError("Task status can only move to in_progress or completed.")
        return value


class IssueTaskAssignSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=FIELD_STAFF, is_active=True)
    )
    due_at = serializers.DateTimeField()
    notes = serializers.CharField(required=False, allow_blank=True)
