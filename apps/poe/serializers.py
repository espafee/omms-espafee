from rest_framework import serializers

from apps.bookings.models import Booking
from apps.tenants.services import get_user_tenant, is_platform_super_admin, require_same_tenant
from core.images import build_public_media_url

from .models import ProofOfExecution, ProofOfExecutionMedia, ProofOfExecutionVerificationLog
from .services import build_location_confidence, get_poe_sla_status, resolve_review_sla_status


class AbsoluteMediaUrlMixin:
    def build_absolute_media_url(self, file_field):
        return build_public_media_url(file_field, request=self.context.get("request"))


class ProofOfExecutionMediaSerializer(AbsoluteMediaUrlMixin, serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProofOfExecutionMedia
        fields = [
            "id",
            "poe_record",
            "image",
            "image_url",
            "provider",
            "media_url",
            "media_type",
            "captured_at",
            "captured_by",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "provider", "captured_by", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["poe_record"].queryset = self.fields["poe_record"].queryset.filter(
                booking__campaign__tenant=get_user_tenant(user)
            )

    def validate(self, attrs):
        image = attrs.get("image")
        media_url = attrs.get("media_url")

        if not image and not media_url:
            raise serializers.ValidationError(
                {"non_field_errors": ["Either an uploaded image or a media URL is required."]}
            )
        request = self.context.get("request")
        user = getattr(request, "user", None)
        poe_record = attrs.get("poe_record") or getattr(self.instance, "poe_record", None)
        if user and poe_record:
            require_same_tenant(user, poe_record.booking.campaign.tenant, message="You can only upload media for your own company POEs.")
        return attrs

    def get_image_url(self, obj):
        return obj.image_url(request=self.context.get("request"), variant="full_preview")


class ProofOfExecutionVerificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProofOfExecutionVerificationLog
        fields = [
            "id",
            "poe_record",
            "verified_by",
            "status_before",
            "status_after",
            "verification_score",
            "distance_meters",
            "threshold_meters",
            "notes",
            "result_payload",
            "created_at",
        ]
        read_only_fields = fields


class ProofOfExecutionSerializer(serializers.ModelSerializer):
    media_items = ProofOfExecutionMediaSerializer(many=True, read_only=True)
    verification_logs = ProofOfExecutionVerificationLogSerializer(many=True, read_only=True)
    location_confidence = serializers.SerializerMethodField()
    review_sla_status = serializers.SerializerMethodField()
    sla_indicator = serializers.SerializerMethodField()

    class Meta:
        model = ProofOfExecution
        fields = [
            "id",
            "booking",
            "client_upload_id",
            "executed_on",
            "captured_at",
            "latitude",
            "longitude",
            "checked_by",
            "verification_status",
            "verification_score",
            "verification_notes",
            "review_comment",
            "review_due_at",
            "reviewed_at",
            "review_sla_status",
            "sla_indicator",
            "notes",
            "location_confidence",
            "media_items",
            "verification_logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "verification_score",
            "verification_notes",
            "reviewed_at",
            "review_sla_status",
            "sla_indicator",
            "location_confidence",
            "media_items",
            "verification_logs",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "client_upload_id": {"validators": []},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["booking"].queryset = self.fields["booking"].queryset.filter(campaign__tenant=get_user_tenant(user))
            self.fields["checked_by"].queryset = self.fields["checked_by"].queryset.filter(tenant=get_user_tenant(user))

    def validate_booking(self, value: Booking):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.campaign.tenant, message="You can only upload POE for your own company bookings.")
        return value

    def get_location_confidence(self, obj):
        return build_location_confidence(obj)

    def get_review_sla_status(self, obj):
        return resolve_review_sla_status(obj)

    def get_sla_indicator(self, obj):
        return get_poe_sla_status(obj)


class ProofOfExecutionApproveRequestSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ProofOfExecutionVerifyRequestSerializer(serializers.Serializer):
    poe_record = serializers.PrimaryKeyRelatedField(queryset=ProofOfExecution.objects.all())
    distance_threshold_meters = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default="250.00",
        min_value=0,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not is_platform_super_admin(user):
            self.fields["poe_record"].queryset = self.fields["poe_record"].queryset.filter(
                booking__campaign__tenant=get_user_tenant(user)
            )

    def validate_poe_record(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user:
            require_same_tenant(user, value.booking.campaign.tenant, message="You can only verify POEs in your own company.")
        return value


class ProofOfExecutionRejectRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ProofOfExecutionVerifyResponseSerializer(serializers.Serializer):
    poe_record = serializers.IntegerField()
    verification_status = serializers.CharField()
    verification_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    verification_notes = serializers.CharField()
    suspicious = serializers.BooleanField()
    distance_meters = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    threshold_meters = serializers.DecimalField(max_digits=10, decimal_places=2)
    image_comparison = serializers.DictField()
    content_validation = serializers.DictField()
