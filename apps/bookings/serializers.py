from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.tenants.services import get_user_tenant, is_platform_super_admin, require_same_tenant
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            tenant = get_user_tenant(user)
            self.fields["campaign"].queryset = self.fields["campaign"].queryset.filter(tenant=tenant)
            self.fields["media_unit"].queryset = self.fields["media_unit"].queryset.filter(site__tenant=tenant)
            self.fields["assigned_user_id"].queryset = self.fields["assigned_user_id"].queryset.filter(tenant=tenant)
            self.fields["field_staff_user_id"].queryset = self.fields["field_staff_user_id"].queryset.filter(tenant=tenant)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        campaign = attrs.get("campaign") or getattr(self.instance, "campaign", None)
        media_unit = attrs.get("media_unit") or getattr(self.instance, "media_unit", None)
        assigned_user = attrs.get("assigned_user")
        if user and campaign:
            require_same_tenant(user, campaign.tenant, message="You can only manage bookings for your own company campaigns.")
        if campaign and media_unit and campaign.tenant_id != media_unit.site.tenant_id:
            raise serializers.ValidationError({"media_unit": "Media unit must belong to the same tenant as the campaign."})
        if assigned_user and campaign and assigned_user.tenant_id != campaign.tenant_id:
            raise serializers.ValidationError({"assigned_user_id": "Assigned user must belong to the campaign tenant."})
        return attrs

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
