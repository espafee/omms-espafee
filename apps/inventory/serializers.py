from rest_framework import serializers

from .models import MediaSite, MediaSiteImage, MediaUnit, MediaUnitImage, RateCard


class AbsoluteMediaUrlMixin:
    def build_absolute_media_url(self, file_field):
        if not file_field:
            return None

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(file_field.url)
        return file_field.url


class MediaSiteImageSerializer(AbsoluteMediaUrlMixin, serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaSiteImage
        fields = [
            "id",
            "site",
            "image",
            "image_url",
            "caption",
            "is_primary",
            "uploaded_by",
            "uploaded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "uploaded_by", "uploaded_at", "created_at", "updated_at"]

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)


class MediaUnitImageSerializer(AbsoluteMediaUrlMixin, serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MediaUnitImage
        fields = [
            "id",
            "media_unit",
            "image",
            "image_url",
            "caption",
            "is_primary",
            "uploaded_by",
            "uploaded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "uploaded_by", "uploaded_at", "created_at", "updated_at"]

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)


class MediaSiteSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    image_gallery = MediaSiteImageSerializer(many=True, read_only=True, source="images")

    class Meta:
        model = MediaSite
        fields = [
            "id",
            "name",
            "code",
            "site_type",
            "address",
            "city",
            "state",
            "latitude",
            "longitude",
            "owner",
            "primary_image",
            "image_gallery",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "primary_image", "image_gallery", "created_at", "updated_at"]

    def get_primary_image(self, obj):
        image = obj.primary_image_object
        if not image:
            return None
        return MediaSiteImageSerializer(instance=image, context=self.context).data


class MediaUnitSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    image_gallery = MediaUnitImageSerializer(many=True, read_only=True, source="images")

    class Meta:
        model = MediaUnit
        fields = [
            "id",
            "site",
            "unit_code",
            "face_count",
            "width",
            "height",
            "status",
            "is_illuminated",
            "monthly_rate",
            "facing_direction",
            "site_type",
            "primary_image",
            "image_gallery",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "primary_image", "image_gallery", "created_at", "updated_at"]

    def get_primary_image(self, obj):
        image = obj.primary_image_object
        if not image:
            return None
        return MediaUnitImageSerializer(instance=image, context=self.context).data


class RateCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateCard
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
