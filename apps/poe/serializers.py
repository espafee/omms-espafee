from rest_framework import serializers

from .models import ProofOfExecution, ProofOfExecutionMedia, ProofOfExecutionVerificationLog


class AbsoluteMediaUrlMixin:
    def build_absolute_media_url(self, file_field):
        if not file_field:
            return None

        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(file_field.url)
        return file_field.url


class ProofOfExecutionMediaSerializer(AbsoluteMediaUrlMixin, serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProofOfExecutionMedia
        fields = [
            "id",
            "poe_record",
            "image",
            "image_url",
            "media_url",
            "media_type",
            "captured_at",
            "captured_by",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "captured_by", "created_at", "updated_at"]

    def validate(self, attrs):
        image = attrs.get("image")
        media_url = attrs.get("media_url")

        if not image and not media_url:
            raise serializers.ValidationError(
                {"non_field_errors": ["Either an uploaded image or a media URL is required."]}
            )
        return attrs

    def get_image_url(self, obj):
        return self.build_absolute_media_url(obj.image)


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

    class Meta:
        model = ProofOfExecution
        fields = [
            "id",
            "booking",
            "executed_on",
            "captured_at",
            "latitude",
            "longitude",
            "checked_by",
            "verification_status",
            "verification_score",
            "verification_notes",
            "notes",
            "media_items",
            "verification_logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "verification_score",
            "verification_notes",
            "media_items",
            "verification_logs",
            "created_at",
            "updated_at",
        ]


class ProofOfExecutionVerifyRequestSerializer(serializers.Serializer):
    poe_record = serializers.PrimaryKeyRelatedField(queryset=ProofOfExecution.objects.all())
    distance_threshold_meters = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default="250.00",
        min_value=0,
    )


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
