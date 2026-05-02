from rest_framework import serializers

from apps.bookings.models import Assignment, Booking
from core.images import build_public_media_url
from core.roles import FIELD_STAFF

from .models import Issue


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
            "status",
            "priority",
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
            "created_at",
            "updated_at",
            "resolved_at",
        ]

    def get_image_url(self, obj):
        return build_public_media_url(obj.image, request=self.context.get("request"))

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
        if getattr(user, "role", None) == FIELD_STAFF and reporter_type != Issue.ReporterType.FIELD_STAFF:
            raise serializers.ValidationError("Field staff must report as field_staff.")
        if reporter_type == Issue.ReporterType.CLIENT:
            raise serializers.ValidationError("Client issue reporting is not enabled yet.")
        return reporter_type
