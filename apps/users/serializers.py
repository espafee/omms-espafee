from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.tenants.services import is_platform_super_admin

from .services import UserService

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_type = serializers.CharField(source="tenant.tenant_type", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "role",
            "organization_name",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "tenant_type",
            "is_platform_admin",
            "is_company_admin",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "tenant_name",
            "tenant_slug",
            "tenant_type",
            "is_platform_admin",
            "is_company_admin",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        ]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.email

    def validate_tenant(self, value):
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return value
        if is_platform_super_admin(request.user):
            return value
        if value != getattr(request.user, "tenant", None):
            raise serializers.ValidationError("Company admins can only manage users in their own company.")
        return value


class ClientOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone_number",
            "organization_name",
        ]
        read_only_fields = fields


class FieldStaffOptionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "role",
        ]
        read_only_fields = fields

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.email

    def get_name(self, obj) -> str:
        return obj.get_full_name() or obj.email


class ClientCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="A user with this email already exists.")]
    )
    username = serializers.CharField(
        validators=[UniqueValidator(queryset=User.objects.all(), message="A user with this username already exists.")]
    )
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone_number",
            "organization_name",
            "password",
            "is_active",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False) and "tenant" not in validated_data:
            validated_data["tenant"] = getattr(request.user, "tenant", None)
        return UserService().register_user(role=User.Role.CLIENT, **validated_data)


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone_number",
            "organization_name",
            "password",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return UserService().register_user(**validated_data)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["tenant_id"] = user.tenant_id
        token["tenant_slug"] = user.tenant.slug if user.tenant_id else ""
        token["tenant_type"] = user.tenant.tenant_type if user.tenant_id else ""
        token["is_platform_admin"] = user.is_platform_admin
        token["is_company_admin"] = user.is_company_admin
        token["is_staff"] = user.is_staff
        token["is_superuser"] = user.is_superuser
        return token

    def validate(self, attrs):
        login_identifier = attrs.get(self.username_field, "")
        if login_identifier and "@" not in login_identifier:
            user = User.objects.filter(username__iexact=login_identifier).only("email").first()
            if user:
                attrs[self.username_field] = user.email

        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
