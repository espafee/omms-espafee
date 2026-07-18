from django.utils import timezone
from rest_framework import serializers

from core.images import build_public_media_url
from apps.tenants.services import get_user_tenant, is_platform_super_admin, require_same_tenant

from .models import MediaSite, MediaSiteImage, MediaUnit, MediaUnitImage, RateCard


class AbsoluteMediaUrlMixin:
    def build_absolute_media_url(self, file_field):
        return build_public_media_url(file_field, request=self.context.get("request"))


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["site"].queryset = self.fields["site"].queryset.filter(tenant=get_user_tenant(user))

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)

    def validate_site(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.tenant, message="You can only upload images for your own company sites.")
        return value


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["media_unit"].queryset = self.fields["media_unit"].queryset.filter(site__tenant=get_user_tenant(user))

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)

    def validate_media_unit(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.site.tenant, message="You can only upload images for your own company units.")
        return value


class MediaSiteSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    image_gallery = MediaSiteImageSerializer(many=True, read_only=True, source="images")

    class Meta:
        model = MediaSite
        fields = [
            "id",
            "tenant",
            "name",
            "code",
            "site_type",
            "address",
            "city",
            "state",
            "latitude",
            "longitude",
            "location_status",
            "location_source",
            "location_verified_at",
            "location_verified_by",
            "owner",
            "primary_image",
            "image_gallery",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "location_status",
            "location_source",
            "location_verified_at",
            "location_verified_by",
            "primary_image",
            "image_gallery",
            "created_at",
            "updated_at",
        ]

    def validate_tenant(self, value):
        actor = self._actor()
        if actor and is_platform_super_admin(actor):
            return value
        if actor and value and value != get_user_tenant(actor):
            raise serializers.ValidationError("Company users can only use their own tenant.")
        return value

    def get_primary_image(self, obj):
        image = obj.primary_image_object
        if not image:
            return None
        return MediaSiteImageSerializer(instance=image, context=self.context).data

    def _actor(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return user if user and user.is_authenticated else None

    def _apply_manual_location_metadata(self, instance, *, latitude_changed: bool, longitude_changed: bool):
        if not (latitude_changed or longitude_changed):
            return
        if instance.latitude is None or instance.longitude is None:
            instance.location_status = MediaSite.LocationStatus.UNVERIFIED
            instance.location_source = ""
            instance.location_verified_at = None
            instance.location_verified_by = None
            return

        actor = self._actor()
        is_admin = bool(actor and (actor.is_staff or actor.is_superuser or getattr(actor, "role", "") == "admin"))
        instance.location_status = MediaSite.LocationStatus.VERIFIED if is_admin else MediaSite.LocationStatus.PROVISIONAL
        instance.location_source = (
            MediaSite.LocationSource.ADMIN_VERIFIED if is_admin else MediaSite.LocationSource.MANUAL
        )
        instance.location_verified_at = timezone.now() if is_admin else None
        instance.location_verified_by = actor if is_admin else None

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._apply_manual_location_metadata(
            instance,
            latitude_changed=instance.latitude is not None,
            longitude_changed=instance.longitude is not None,
        )
        if instance.location_source or instance.location_status != MediaSite.LocationStatus.UNVERIFIED:
            instance.save(
                update_fields=[
                    "location_status",
                    "location_source",
                    "location_verified_at",
                    "location_verified_by",
                    "updated_at",
                ]
            )
        return instance

    def update(self, instance, validated_data):
        latitude_changed = "latitude" in validated_data and validated_data.get("latitude") != instance.latitude
        longitude_changed = "longitude" in validated_data and validated_data.get("longitude") != instance.longitude
        instance = super().update(instance, validated_data)
        self._apply_manual_location_metadata(
            instance,
            latitude_changed=latitude_changed,
            longitude_changed=longitude_changed,
        )
        if latitude_changed or longitude_changed:
            instance.save(
                update_fields=[
                    "location_status",
                    "location_source",
                    "location_verified_at",
                    "location_verified_by",
                    "updated_at",
                ]
            )
        return instance


class MediaUnitSerializer(serializers.ModelSerializer):
    primary_image = serializers.SerializerMethodField()
    image_gallery = MediaUnitImageSerializer(many=True, read_only=True, source="images")

    class Meta:
        model = MediaUnit
        fields = [
            "id",
            "public_id",
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
            "is_publicly_listed",
            "public_description",
            "public_features",
            "primary_image",
            "image_gallery",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "public_id", "primary_image", "image_gallery", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["site"].queryset = self.fields["site"].queryset.filter(tenant=get_user_tenant(user))

    def get_primary_image(self, obj):
        image = obj.primary_image_object
        if not image:
            return None
        return MediaUnitImageSerializer(instance=image, context=self.context).data

    def validate_site(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.tenant, message="You can only use sites from your own company.")
        return value


class InventorySiteListSerializer(AbsoluteMediaUrlMixin, serializers.ModelSerializer):
    site_id = serializers.IntegerField(source="id", read_only=True)
    site_code = serializers.CharField(source="code", read_only=True)
    title = serializers.CharField(source="name", read_only=True)
    media_type = serializers.CharField(source="site_type", read_only=True)
    unit_ids = serializers.SerializerMethodField()
    unit_codes = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()
    facing_direction = serializers.SerializerMethodField()
    unit_site_type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()
    available_unit_count = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()
    has_coordinates = serializers.SerializerMethodField()

    class Meta:
        model = MediaSite
        fields = [
            "id",
            "site_id",
            "site_code",
            "unit_ids",
            "unit_codes",
            "title",
            "address",
            "city",
            "state",
            "media_type",
            "dimensions",
            "facing_direction",
            "unit_site_type",
            "status",
            "thumbnail_url",
            "unit_count",
            "available_unit_count",
            "image_count",
            "has_coordinates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _units(self, obj):
        return list(obj.units.all())

    def _distinct_values(self, obj, attribute):
        values = []
        for unit in self._units(obj):
            value = getattr(unit, attribute, "")
            if value and value not in values:
                values.append(value)
        return values

    def get_unit_ids(self, obj):
        return [unit.id for unit in self._units(obj)]

    def get_unit_codes(self, obj):
        return self._distinct_values(obj, "unit_code")

    def get_dimensions(self, obj):
        values = []
        for unit in self._units(obj):
            value = f"{unit.width} x {unit.height}"
            if value not in values:
                values.append(value)
        return ", ".join(values) if values else ""

    def get_facing_direction(self, obj):
        return ", ".join(self._distinct_values(obj, "facing_direction"))

    def get_unit_site_type(self, obj):
        return ", ".join(self._distinct_values(obj, "site_type"))

    def get_status(self, obj):
        statuses = self._distinct_values(obj, "status")
        if not statuses:
            return "no_units"
        for status_value in [
            MediaUnit.Status.AVAILABLE,
            MediaUnit.Status.RESERVED,
            MediaUnit.Status.MAINTENANCE,
            MediaUnit.Status.RETIRED,
        ]:
            if status_value in statuses:
                return status_value
        return statuses[0]

    def get_thumbnail_url(self, obj):
        images = list(obj.images.all())
        image = next((item for item in images if item.is_primary), None) or (images[0] if images else None)
        if not image:
            for unit in self._units(obj):
                unit_images = list(unit.images.all())
                image = next((item for item in unit_images if item.is_primary), None) or (unit_images[0] if unit_images else None)
                if image:
                    break
        if not image:
            return None
        return self.build_absolute_media_url(image.image)

    def get_unit_count(self, obj):
        return len(self._units(obj))

    def get_available_unit_count(self, obj):
        return sum(unit.status == MediaUnit.Status.AVAILABLE for unit in self._units(obj))

    def get_image_count(self, obj):
        return len(list(obj.images.all()))

    def get_has_coordinates(self, obj):
        return obj.latitude is not None and obj.longitude is not None


class InventoryUnitListSerializer(AbsoluteMediaUrlMixin, serializers.ModelSerializer):
    location_id = serializers.IntegerField(source="site_id", read_only=True)
    location_name = serializers.CharField(source="site.name", read_only=True)
    location_code = serializers.CharField(source="site.code", read_only=True)
    city = serializers.CharField(source="site.city", read_only=True)
    address = serializers.CharField(source="site.address", read_only=True)
    location_type = serializers.CharField(source="site.site_type", read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = MediaUnit
        fields = [
            "id",
            "public_id",
            "unit_code",
            "location_id",
            "location_name",
            "location_code",
            "city",
            "address",
            "location_type",
            "face_count",
            "width",
            "height",
            "status",
            "is_illuminated",
            "monthly_rate",
            "facing_direction",
            "site_type",
            "is_publicly_listed",
            "thumbnail_url",
            "image_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _images(self, obj):
        return list(obj.images.all())

    def get_thumbnail_url(self, obj):
        images = self._images(obj)
        image = next((item for item in images if item.is_primary), None) or (images[0] if images else None)
        if not image:
            location_images = list(obj.site.images.all())
            image = next((item for item in location_images if item.is_primary), None) or (location_images[0] if location_images else None)
        return self.build_absolute_media_url(image.image) if image else None

    def get_image_count(self, obj):
        return len(self._images(obj))


class RateCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateCard
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["unit"].queryset = self.fields["unit"].queryset.filter(site__tenant=get_user_tenant(user))
