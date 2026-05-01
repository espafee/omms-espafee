from __future__ import annotations

from rest_framework import serializers


class AssignedWorkSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    campaign_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    site_id = serializers.IntegerField()
    site_name = serializers.CharField()
    unit_id = serializers.IntegerField()
    unit_name = serializers.CharField()
    location = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    booking_start = serializers.DateField()
    booking_end = serializers.DateField()
    poe_status = serializers.CharField()


class MobilePoeSubmitSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    image = serializers.ImageField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    captured_at = serializers.DateTimeField()
    notes = serializers.CharField(required=False, allow_blank=True)


class MobilePoeSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    poe_id = serializers.IntegerField()
    status = serializers.CharField()
    distance_meters = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
