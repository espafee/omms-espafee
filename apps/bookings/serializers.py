from rest_framework import serializers
from django.contrib.auth import get_user_model

from core.roles import FIELD_ASSIGNABLE_ROLES

from .models import Assignment, Booking

User = get_user_model()


class BookingSummarySerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    live_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    unique_media_units = serializers.IntegerField()
    total_booked_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    live_booked_value = serializers.DecimalField(max_digits=14, decimal_places=2)


class BookingSerializer(serializers.ModelSerializer):
    assigned_user = serializers.SerializerMethodField()
    assigned_user_id = serializers.PrimaryKeyRelatedField(
        source="assigned_user",
        queryset=User.objects.filter(role__in=FIELD_ASSIGNABLE_ROLES, is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    field_staff_user_id = serializers.PrimaryKeyRelatedField(
        source="assigned_user",
        queryset=User.objects.filter(role__in=FIELD_ASSIGNABLE_ROLES, is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_assigned_user(self, obj):
        assignment = next(
            (assignment for assignment in obj.assignments.all() if assignment.status != Assignment.Status.CANCELLED),
            None,
        )
        if not assignment:
            return None
        user = assignment.user
        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.get_full_name() or user.email,
            "role": user.role,
            "assignment_status": assignment.status,
            "assigned_at": assignment.assigned_at,
        }
