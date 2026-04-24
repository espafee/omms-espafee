from rest_framework import serializers

from .models import Booking


class BookingSummarySerializer(serializers.Serializer):
    total_bookings = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    live_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    unique_media_units = serializers.IntegerField()
    total_booked_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    live_booked_value = serializers.DecimalField(max_digits=14, decimal_places=2)


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
