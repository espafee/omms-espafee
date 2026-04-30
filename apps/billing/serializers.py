from rest_framework import serializers

from .models import Invoice, InvoiceLine, InvoiceSequence, Payment, SupplierProfile


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
