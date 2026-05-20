from rest_framework import serializers

from apps.inventory.serializers import AbsoluteMediaUrlMixin
from apps.tenants.services import get_user_tenant, is_platform_super_admin, require_same_tenant

from .models import Campaign, CampaignAccessToken, CampaignAsset
from .services import build_campaign_performance_analytics


class CampaignSummarySerializer(serializers.Serializer):
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
    draft_campaigns = serializers.IntegerField()
    completed_campaigns = serializers.IntegerField()
    total_budget = serializers.DecimalField(max_digits=14, decimal_places=2)
    active_budget = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_bookings = serializers.IntegerField()
    live_bookings = serializers.IntegerField()
    approved_assets = serializers.IntegerField()
    ending_soon_count = serializers.IntegerField()
    campaigns_at_risk = serializers.IntegerField()
    campaigns_poe_risk = serializers.IntegerField()
    campaigns_billing_risk = serializers.IntegerField()
    critical_campaigns = serializers.IntegerField()


class CampaignAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignAsset
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["campaign"].queryset = self.fields["campaign"].queryset.filter(tenant=get_user_tenant(user))

    def validate_campaign(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.tenant, message="You can only add assets to campaigns in your own company.")
        return value


class CampaignSerializer(serializers.ModelSerializer):
    assets = CampaignAssetSerializer(many=True, read_only=True)
    performance = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            tenant = get_user_tenant(user)
            self.fields["client"].queryset = self.fields["client"].queryset.filter(tenant=tenant)
            self.fields["account_manager"].queryset = self.fields["account_manager"].queryset.filter(tenant=tenant)

    def validate_tenant(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and is_platform_super_admin(user):
            return value
        if user and value and value != get_user_tenant(user):
            raise serializers.ValidationError("Company users can only use their own tenant.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None) or get_user_tenant(user)
        for field in ("client", "account_manager"):
            related_user = attrs.get(field) or getattr(self.instance, field, None)
            if related_user and tenant and related_user.tenant_id != tenant.id:
                raise serializers.ValidationError({field: "Campaign users must belong to the campaign tenant."})
        return attrs

    def get_performance(self, obj):
        user = self.context.get("request").user if self.context.get("request") else None
        payload = build_campaign_performance_analytics(user=user, queryset=Campaign.objects.filter(id=obj.id))
        return payload["campaigns"][0] if payload["campaigns"] else None


class CampaignAccessTokenSerializer(serializers.ModelSerializer):
    public_path = serializers.SerializerMethodField()

    def get_public_path(self, obj):
        return obj.public_path

    class Meta:
        model = CampaignAccessToken
        fields = [
            "id",
            "campaign",
            "public_path",
            "token_prefix",
            "is_active",
            "expires_at",
            "revoked_at",
            "created_by",
            "revoked_by",
            "last_accessed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CampaignAccessTokenCreateSerializer(serializers.Serializer):
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["campaign"].queryset = self.fields["campaign"].queryset.filter(tenant=get_user_tenant(user))

    def validate_campaign(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.tenant, message="You can only share campaigns in your own company.")
        return value


class CampaignAccessTokenCreateResponseSerializer(CampaignAccessTokenSerializer):
    token = serializers.CharField(source="token_value")

    class Meta(CampaignAccessTokenSerializer.Meta):
        fields = CampaignAccessTokenSerializer.Meta.fields + ["token"]
        read_only_fields = fields


class PublicAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignAsset
        fields = ["id", "name", "asset_type", "file_url", "version"]
        read_only_fields = fields


class PublicImageSerializer(AbsoluteMediaUrlMixin, serializers.Serializer):
    id = serializers.IntegerField()
    image_url = serializers.SerializerMethodField()
    caption = serializers.CharField()
    is_primary = serializers.BooleanField()

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)


class PublicSiteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    primary_image = serializers.SerializerMethodField()

    def get_primary_image(self, obj):
        image = obj.primary_image_object
        if not image:
            return None
        return PublicImageSerializer(instance=image, context=self.context).data


class PublicMediaUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    unit_code = serializers.CharField()
    status = serializers.CharField()
    is_illuminated = serializers.BooleanField()
    facing_direction = serializers.CharField(allow_blank=True)
    site_type = serializers.CharField(allow_blank=True)
    primary_image = serializers.SerializerMethodField()

    def get_primary_image(self, obj):
        image = obj.primary_image_object
        if not image:
            return None
        return PublicImageSerializer(instance=image, context=self.context).data


class PublicProofOfExecutionMediaSerializer(AbsoluteMediaUrlMixin, serializers.Serializer):
    id = serializers.IntegerField()
    image_url = serializers.SerializerMethodField()
    media_url = serializers.CharField(allow_blank=True)
    media_type = serializers.CharField()
    captured_at = serializers.DateTimeField()

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)


class PublicProofOfExecutionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    executed_on = serializers.DateField()
    captured_at = serializers.DateTimeField()
    verification_status = serializers.CharField()
    verification_score = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    verification_notes = serializers.CharField()
    media_items = PublicProofOfExecutionMediaSerializer(many=True)


class PublicBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    site = PublicSiteSerializer(source="media_unit.site")
    media_unit = PublicMediaUnitSerializer()
    poe_records = PublicProofOfExecutionSerializer(many=True)


class PublicCampaignDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()
    status = serializers.CharField()
    objective = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    assets = serializers.SerializerMethodField()
    bookings = PublicBookingSerializer(many=True)

    def get_assets(self, obj):
        assets = [asset for asset in obj.assets.all() if asset.is_approved]
        return PublicAssetSerializer(instance=assets, many=True, context=self.context).data


class PublicCampaignAccessSerializer(serializers.Serializer):
    campaign = PublicCampaignDetailSerializer()
    access_expires_at = serializers.DateTimeField(allow_null=True)
    link_status = serializers.CharField()
