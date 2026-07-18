from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from apps.tenants.models import Tenant
from apps.tenants.services import is_platform_super_admin
from .team_services import TEAM_ROLE_DEFINITIONS, available_team_tenants

User = get_user_model()


class TeamUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    reports_to_name = serializers.SerializerMethodField()
    assigned_work_count = serializers.IntegerField(read_only=True, default=0)
    managed_campaign_count = serializers.IntegerField(read_only=True, default=0)
    assigned_work_summary = serializers.SerializerMethodField()
    account_status = serializers.SerializerMethodField()
    has_usable_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "role",
            "role_label",
            "region",
            "reports_to",
            "reports_to_name",
            "tenant",
            "tenant_name",
            "assigned_work_count",
            "managed_campaign_count",
            "assigned_work_summary",
            "last_login",
            "is_active",
            "account_status",
            "has_usable_password",
            "setup_sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_reports_to_name(self, obj):
        if not obj.reports_to_id:
            return ""
        return obj.reports_to.get_full_name() or obj.reports_to.email

    def get_assigned_work_summary(self, obj):
        work_count = getattr(obj, "assigned_work_count", 0)
        campaign_count = getattr(obj, "managed_campaign_count", 0)
        parts = []
        if work_count:
            parts.append(f"{work_count} assigned task{'s' if work_count != 1 else ''}")
        if campaign_count:
            parts.append(f"{campaign_count} managed campaign{'s' if campaign_count != 1 else ''}")
        return " · ".join(parts) if parts else "No active assignments"

    def get_account_status(self, obj):
        if not obj.is_active:
            return "inactive"
        return "active" if obj.has_usable_password() else "setup_pending"

    def get_has_usable_password(self, obj):
        return obj.has_usable_password()


class TeamUserWriteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    role = serializers.CharField(required=False, max_length=20)
    region = serializers.CharField(required=False, allow_blank=True, max_length=120)
    reports_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all(), required=False)
    send_setup = serializers.BooleanField(required=False, default=True, write_only=True)

    def validate(self, attrs):
        request = self.context["request"]
        instance = self.context.get("instance")
        if instance is None:
            for field in ("email", "role"):
                if field not in attrs:
                    raise serializers.ValidationError({field: ["This field is required."]})
        elif "email" in attrs and attrs["email"].lower() != instance.email.lower():
            raise serializers.ValidationError({"email": ["Changing a user's login email is not supported."]})

        tenant = attrs.get("tenant", getattr(instance, "tenant", None))
        if not is_platform_super_admin(request.user):
            if instance is not None and tenant is not None and tenant != request.user.tenant:
                raise serializers.ValidationError({"tenant": ["You can only manage users inside your own company."]})
            if tenant is None:
                attrs["tenant"] = request.user.tenant
                tenant = request.user.tenant
        if instance is not None and tenant is not None and tenant != instance.tenant:
            raise serializers.ValidationError({"tenant": ["Moving an existing user between companies is not supported."]})

        reports_to = attrs.get("reports_to")
        if reports_to is not None and tenant is not None and reports_to.tenant_id != tenant.id:
            raise serializers.ValidationError({"reports_to": ["The reporting manager must belong to the same company."]})
        return attrs


class TeamRolesSerializer(serializers.Serializer):
    roles = serializers.ListField(child=serializers.DictField())
    tenants = serializers.ListField(child=serializers.DictField())
    can_select_tenant = serializers.BooleanField()

    @classmethod
    def for_actor(cls, actor):
        return {
            "roles": list(TEAM_ROLE_DEFINITIONS),
            "tenants": [
                {"id": tenant.id, "name": tenant.name, "slug": tenant.slug}
                for tenant in available_team_tenants(actor)
            ],
            "can_select_tenant": is_platform_super_admin(actor),
        }


class PasswordSetupCompleteSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=10, trim_whitespace=False)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": ["This account setup link is invalid or has expired."]})
        from django.contrib.auth.tokens import default_token_generator

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": ["This account setup link is invalid or has expired."]})
        validate_password(attrs["password"], user=user)
        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password", "updated_at"])
        return user
