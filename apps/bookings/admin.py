from django.contrib import admin

from .models import Assignment, Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("campaign", "media_unit", "start_date", "end_date", "booked_rate", "status")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("campaign__name", "campaign__code", "media_unit__unit_code")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("booking", "user", "assigned_by", "assigned_at", "status")
    list_filter = ("status", "assigned_at")
    search_fields = ("booking__campaign__name", "booking__media_unit__unit_code", "user__email", "user__username")
