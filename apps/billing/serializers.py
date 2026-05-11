from decimal import Decimal

from rest_framework import serializers

from apps.campaigns.models import Campaign

from .models import CampaignEstimate, CampaignEstimateLine, Invoice, InvoiceEvent, InvoiceLine, InvoiceSequence, Payment, SupplierProfile
from .services import get_invoice_payment_status


class InvoiceSummarySerializer(serializers.Serializer):
    total_estimated = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_approved_estimates = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_invoices = serializers.IntegerField()
    draft_invoices = serializers.IntegerField()
    issued_invoices = serializers.IntegerField()
    due_soon_invoices = serializers.IntegerField()
    overdue_invoices = serializers.IntegerField()
    paid_invoices = serializers.IntegerField()
    partially_paid_invoices = serializers.IntegerField()
    payment_count = serializers.IntegerField()
    total_invoiced = serializers.DecimalField(max_digits=14, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    payments_received_this_month = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_collected = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=14, decimal_places=2)


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
    payment_mode = serializers.CharField(source="method", required=False)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "payment_date",
            "amount",
            "method",
            "payment_mode",
            "reference_number",
            "notes",
            "recorded_by",
            "recorded_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "recorded_by", "recorded_by_name", "created_at", "updated_at"]

    def get_recorded_by_name(self, obj):
        user = obj.recorded_by
        if not user:
            return ""
        return user.get_full_name() or user.organization_name or user.email or user.username


class InvoicePaymentCreateSerializer(serializers.ModelSerializer):
    payment_mode = serializers.CharField(source="method", required=False)

    class Meta:
        model = Payment
        fields = ["amount", "payment_date", "payment_mode", "reference_number", "notes"]


class InvoiceCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=500)


class InvoiceEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceEvent
        fields = [
            "id",
            "invoice",
            "event_type",
            "actor",
            "actor_name",
            "from_status",
            "to_status",
            "message",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        user = obj.actor
        if not user:
            return ""
        return user.get_full_name() or user.organization_name or user.email or user.username


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
    public_path = serializers.SerializerMethodField()

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
            "rejected_at",
            "approval_token_value",
            "approval_token_hash",
            "approval_token_prefix",
            "approval_token_created_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_client_name(self, obj):
        return obj.client.organization_name or obj.client.get_full_name() or obj.client.email

    def get_public_path(self, obj):
        return obj.public_path


class PublicCampaignEstimateLineSerializer(serializers.ModelSerializer):
    media_unit_label = serializers.SerializerMethodField()
    site_name = serializers.SerializerMethodField()

    class Meta:
        model = CampaignEstimateLine
        fields = [
            "id",
            "description",
            "start_date",
            "end_date",
            "quantity",
            "unit_rate",
            "tax_rate",
            "taxable_amount",
            "tax_amount",
            "total_amount",
            "media_unit_label",
            "site_name",
        ]

    def get_media_unit_label(self, obj):
        if not obj.media_unit:
            return ""
        return obj.media_unit.unit_code

    def get_site_name(self, obj):
        if not obj.media_unit:
            return ""
        return obj.media_unit.site.name


class PublicCampaignEstimateSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)
    lines = PublicCampaignEstimateLineSerializer(many=True, read_only=True)

    class Meta:
        model = CampaignEstimate
        fields = [
            "id",
            "estimate_number",
            "title",
            "status",
            "start_date",
            "end_date",
            "subtotal",
            "tax_amount",
            "total_amount",
            "notes",
            "client_name",
            "campaign_name",
            "shared_at",
            "approved_at",
            "rejected_at",
            "client_response_comment",
            "lines",
        ]

    def get_client_name(self, obj):
        return obj.client.organization_name or obj.client.get_full_name() or obj.client.email


class PublicEstimateDecisionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)


class GenerateInvoiceFromBookingsSerializer(serializers.Serializer):
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    supplier_profile = serializers.PrimaryKeyRelatedField(queryset=SupplierProfile.objects.filter(is_active=True), required=False, allow_null=True)
    invoice_date = serializers.DateField(required=False)
    due_date = serializers.DateField()
    payment_terms = serializers.CharField(required=False, allow_blank=True)
    gst_rate = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    sac_code = serializers.CharField(required=False, allow_blank=True, default="998361")


class InvoiceSerializer(serializers.ModelSerializer):
    pdf_file = serializers.SerializerMethodField()
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    events = InvoiceEventSerializer(many=True, read_only=True)
    invoice_total = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    def get_pdf_file(self, obj):
        return obj.pdf_file.name if obj.pdf_file else None

    def get_invoice_total(self, obj):
        return obj.grand_total or obj.total_amount

    def get_amount_paid(self, obj):
        return sum((payment.amount for payment in obj.payments.all()), Decimal("0.00"))

    def get_balance_due(self, obj):
        invoice_total = self.get_invoice_total(obj) or Decimal("0.00")
        amount_paid = self.get_amount_paid(obj)
        return max(invoice_total - amount_paid, Decimal("0.00"))

    def get_payment_status(self, obj):
        return get_invoice_payment_status(obj, total_paid=self.get_amount_paid(obj))

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


class ClientStatementSerializer(serializers.Serializer):
    client_id = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    total_billed = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    unpaid_invoices = InvoiceSerializer(many=True)
    payments = PaymentSerializer(many=True)

    def get_client_id(self, obj):
        return obj["client"].id

    def get_client_name(self, obj):
        client = obj["client"]
        return client.organization_name or client.get_full_name() or client.email or client.username
