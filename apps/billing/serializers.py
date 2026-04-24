from rest_framework import serializers

from .models import Invoice, InvoiceLine, Payment


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
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
