from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("campaign", "media_unit", "start_date", "end_date", "booked_rate", "status")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("campaign__name", "campaign__code", "media_unit__unit_code")
