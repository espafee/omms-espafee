from django.db import models

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from core.models import TimeStampedModel


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"

    campaign = models.ForeignKey(Campaign, related_name="invoices", on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    def __str__(self) -> str:
        return self.invoice_number


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    booking = models.ForeignKey(
        Booking,
        related_name="invoice_lines",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return self.description


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        CHEQUE = "cheque", "Cheque"

    invoice = models.ForeignKey(Invoice, related_name="payments", on_delete=models.CASCADE)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=30, choices=Method.choices)
    reference_number = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:
        return f"{self.invoice.invoice_number} - {self.amount}"
