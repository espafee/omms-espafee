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


class MobileAdminOverviewSerializer(serializers.Serializer):
    active_campaigns = serializers.IntegerField()
    campaigns_at_risk = serializers.IntegerField()
    campaigns_ending_soon = serializers.IntegerField()
    critical_campaigns = serializers.IntegerField()
    poe_pending = serializers.IntegerField()
    poe_completed_today = serializers.IntegerField()
    suspicious_poe = serializers.IntegerField()
    poe_sla_warnings = serializers.IntegerField()
    poe_sla_breaches = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    overdue_invoice_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    collection_efficiency = serializers.IntegerField()
    bookings_starting_today = serializers.IntegerField()
    bookings_ending_today = serializers.IntegerField()
    system_status = serializers.CharField()
    api_status = serializers.CharField()
    environment_mode = serializers.CharField()
    environment_mode_label = serializers.CharField()
    environment_mode_message = serializers.CharField(allow_blank=True)
    environment_write_blocking = serializers.BooleanField()
    failed_jobs = serializers.IntegerField()
    active_alerts = serializers.IntegerField()


class MobileEnvironmentModeSerializer(serializers.Serializer):
    mode = serializers.CharField()
    label = serializers.CharField()
    message = serializers.CharField(allow_blank=True)
    is_write_blocking = serializers.BooleanField()


class MobileAdminRunningCampaignSerializer(serializers.Serializer):
    campaign_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    client_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_units = serializers.IntegerField()
    poe_completed = serializers.IntegerField()
    poe_pending = serializers.IntegerField()
    poe_progress_percent = serializers.IntegerField()
    status = serializers.CharField()


class MobileAdminPoeTrackerSerializer(serializers.Serializer):
    poe_id = serializers.IntegerField()
    booking_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    site_name = serializers.CharField()
    unit_name = serializers.CharField()
    field_staff = serializers.CharField(allow_blank=True)
    submitted_at = serializers.DateTimeField()
    status = serializers.CharField()
    distance_meters = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    image_url = serializers.CharField(allow_null=True, allow_blank=True)


class MobileAdminActivityItemSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    site_name = serializers.CharField()
    unit_name = serializers.CharField()
    assigned_to = serializers.CharField(allow_blank=True)
    due_date = serializers.DateField()
    status = serializers.CharField()


class MobileAdminDailyActivitySerializer(serializers.Serializer):
    date = serializers.DateField()
    installations_due_today = MobileAdminActivityItemSerializer(many=True)
    poe_pending_today = MobileAdminActivityItemSerializer(many=True)
    overdue_items = MobileAdminActivityItemSerializer(many=True)


class MobileAdminAlertSerializer(serializers.Serializer):
    type = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    related_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class MobileAdminSearchResultSerializer(serializers.Serializer):
    module = serializers.CharField()
    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    status = serializers.CharField(allow_blank=True)
    url = serializers.CharField(allow_blank=True)


class MobileAdminIssueSerializer(serializers.Serializer):
    issue_id = serializers.IntegerField()
    booking_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    site_name = serializers.CharField()
    unit_name = serializers.CharField()
    reported_by = serializers.CharField(allow_blank=True)
    issue_type = serializers.CharField()
    description = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField()
    sla_status = serializers.CharField()
    first_response_due_at = serializers.DateTimeField(allow_null=True)
    resolution_due_at = serializers.DateTimeField(allow_null=True)
    image_url = serializers.CharField(allow_null=True, allow_blank=True)
    created_at = serializers.DateTimeField()
