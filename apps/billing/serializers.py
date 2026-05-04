from rest_framework import serializers

from apps.campaigns.models import Campaign

from .models import CampaignEstimate, CampaignEstimateLine, Invoice, InvoiceLine, InvoiceSequence, Payment, SupplierProfile


class InvoiceSummarySerializer(serializers.Serializer):
    total_invoices = serializers.IntegerField()
    issued_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    paid_invoices = serializers.IntegerField()
    partially_paid_invoices = serializers.IntegerField()
    payment_count = serializers.IntegerField()
    total_invoiced = serializers.DecimalField(max_digits=14, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class SupplierProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierProfile
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class InvoiceSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSequence
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class CampaignInvoicePreviewLineSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    line_number = serializers.IntegerField()
    site_name = serializers.CharField()
    media_unit_label = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    media_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    flex_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    installation_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    other_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    cost_notes = serializers.CharField(allow_blank=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    description = serializers.CharField()


class CampaignInvoicePreviewSerializer(serializers.Serializer):
    campaign_id = serializers.IntegerField()
    campaign_name = serializers.CharField()
    campaign_code = serializers.CharField()
    client_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    confirmed_booking_count = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    existing_invoice_id = serializers.IntegerField(allow_null=True)
    existing_invoice_number = serializers.CharField(allow_null=True)
    can_generate = serializers.BooleanField()
    message = serializers.CharField(allow_blank=True)
    lines = CampaignInvoicePreviewLineSerializer(many=True)


class CampaignEstimateLineSerializer(serializers.ModelSerializer):
    media_unit_label = serializers.SerializerMethodField()

    class Meta:
        model = CampaignEstimateLine
        fields = "__all__"
        read_only_fields = ["id", "taxable_amount", "tax_amount", "total_amount", "created_at", "updated_at"]

    def get_media_unit_label(self, obj):
        if not obj.media_unit:
            return ""
        return f"{obj.media_unit.unit_code} - {obj.media_unit.site.name}"


class CampaignEstimateSerializer(serializers.ModelSerializer):
    lines = CampaignEstimateLineSerializer(many=True, read_only=True)
    client_name = serializers.SerializerMethodField()
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = CampaignEstimate
        fields = "__all__"
        read_only_fields = [
            "id",
            "estimate_number",
            "status",
            "subtotal",
            "tax_amount",
            "total_amount",
            "shared_at",
            "approved_at",
            "finalized_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_client_name(self, obj):
        return obj.client.organization_name or obj.client.get_full_name() or obj.client.email


class GenerateInvoiceFromBookingsSerializer(serializers.Serializer):
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    supplier_profile = serializers.PrimaryKeyRelatedField(queryset=SupplierProfile.objects.filter(is_active=True), required=False, allow_null=True)
    invoice_date = serializers.DateField(required=False)
    due_date = serializers.DateField()
    payment_terms = serializers.CharField(required=False, allow_blank=True)
    gst_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default="18.00")
    sac_code = serializers.CharField(required=False, allow_blank=True, default="998361")


class InvoiceSerializer(serializers.ModelSerializer):
    pdf_file = serializers.SerializerMethodField()
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    def get_pdf_file(self, obj):
        return obj.pdf_file.name if obj.pdf_file else None

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "invoice_number",
            "financial_year",
            "status",
            "issued_at",
            "issued_by",
            "cancelled_at",
            "cancelled_by",
            "taxable_value_total",
            "discount_total",
            "cgst_total",
            "sgst_total",
            "igst_total",
            "cess_total",
            "total_tax",
            "grand_total",
            "pdf_file",
        ]
