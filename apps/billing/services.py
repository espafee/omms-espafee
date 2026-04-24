from decimal import Decimal

from django.db import models, transaction
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from core.services import BaseService

from .models import Invoice, Payment
from .repositories import InvoiceLineRepository, InvoiceRepository, PaymentRepository

SUMMARY_DECIMAL_FIELD = DecimalField(max_digits=14, decimal_places=2)


class InvoiceService(BaseService):
    repository_class = InvoiceRepository

    def get_summary(self, user=None):
        invoice_queryset = self.get_queryset(user=user)
        payment_queryset = Payment.objects.filter(invoice__in=invoice_queryset)

        summary = invoice_queryset.aggregate(
            total_invoices=Count("id"),
            issued_invoices=Count("id", filter=Q(status=Invoice.Status.ISSUED)),
            overdue_invoices=Count("id", filter=Q(status=Invoice.Status.OVERDUE)),
            paid_invoices=Count("id", filter=Q(status=Invoice.Status.PAID)),
            partially_paid_invoices=Count("id", filter=Q(status=Invoice.Status.PARTIALLY_PAID)),
            total_invoiced=Coalesce(Sum("total_amount"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD),
            overdue_amount=Coalesce(
                Sum("total_amount", filter=Q(status=Invoice.Status.OVERDUE)),
                Decimal("0.00"),
                output_field=SUMMARY_DECIMAL_FIELD,
            ),
        )
        payment_summary = payment_queryset.aggregate(
            payment_count=Count("id"),
            total_paid=Coalesce(Sum("amount"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD),
        )
        summary.update(payment_summary)
        summary["outstanding_amount"] = max(summary["total_invoiced"] - summary["total_paid"], Decimal("0.00"))
        return summary


class InvoiceLineService(BaseService):
    repository_class = InvoiceLineRepository


class PaymentService(BaseService):
    repository_class = PaymentRepository

    @transaction.atomic
    def create(self, actor=None, **validated_data):
        payment = super().create(actor=actor, **validated_data)
        self._update_invoice_status(payment.invoice)
        return payment

    @transaction.atomic
    def update(self, instance, actor=None, **validated_data):
        payment = super().update(instance, actor=actor, **validated_data)
        self._update_invoice_status(payment.invoice)
        return payment

    def _update_invoice_status(self, invoice):
        total_paid = invoice.payments.aggregate(total=models.Sum("amount")).get("total") or Decimal("0")
        if total_paid <= 0:
            return
        if total_paid >= invoice.total_amount:
            invoice.status = "paid"
        else:
            invoice.status = "partially_paid"
        invoice.save(update_fields=["status", "updated_at"])
