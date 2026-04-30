from __future__ import annotations

from rest_framework import serializers

from core.images import build_public_media_url

from .models import CompanyProfile, OrganizationEmailSettings
from .services import SetupService


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    branding_name = serializers.CharField(read_only=True)

    class Meta:
        model = CompanyProfile
        fields = [
            "id",
            "company_name",
            "legal_name",
            "logo",
            "logo_url",
            "communication_email",
            "phone",
            "address",
            "gstin",
            "state_code",
            "invoice_prefix",
            "bank_details",
            "authorised_signatory",
            "branding_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "branding_name", "created_at", "updated_at", "logo_url"]

    def get_logo_url(self, obj: CompanyProfile) -> str | None:
        return build_public_media_url(obj.logo, request=self.context.get("request"))

    def update(self, instance: CompanyProfile, validated_data):
        return SetupService.update_company_profile(**validated_data)


class OrganizationEmailSettingsSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    has_smtp_password = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationEmailSettings
        fields = [
            "id",
            "from_email",
            "reply_to_email",
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_password",
            "has_smtp_password",
            "use_tls",
            "use_ssl",
            "email_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "has_smtp_password", "email_verified", "created_at", "updated_at"]

    def validate(self, attrs):
        use_tls = attrs.get("use_tls", getattr(self.instance, "use_tls", False))
        use_ssl = attrs.get("use_ssl", getattr(self.instance, "use_ssl", False))
        if use_tls and use_ssl:
            raise serializers.ValidationError("Use either TLS or SSL, not both at the same time.")
        return attrs

    def update(self, instance: OrganizationEmailSettings, validated_data):
        smtp_password = validated_data.pop("smtp_password", None)
        return SetupService.update_email_settings(smtp_password=smtp_password, **validated_data)


class TestEmailSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField(required=False, allow_blank=False)
