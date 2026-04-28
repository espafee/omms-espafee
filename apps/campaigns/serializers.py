from rest_framework import serializers

from apps.inventory.serializers import AbsoluteMediaUrlMixin

from .models import Campaign, CampaignAccessToken, CampaignAsset


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


class CampaignAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignAsset
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class CampaignSerializer(serializers.ModelSerializer):
    assets = CampaignAssetSerializer(many=True, read_only=True)

    class Meta:
        model = Campaign
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


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
