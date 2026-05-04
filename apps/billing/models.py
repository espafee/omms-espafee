import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaUnit
from core.models import TimeStampedModel


class SupplierProfile(TimeStampedModel):
    legal_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    gstin = models.CharField(max_length=15, unique=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    state_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default="India")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    bank_details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["legal_name"]

    def __str__(self) -> str:
        return self.legal_name


class InvoiceSequence(TimeStampedModel):
    class DocumentType(models.TextChoices):
        INVOICE = "INV", "Invoice"

    document_type = models.CharField(max_length=10, choices=DocumentType.choices)
    financial_year = models.CharField(max_length=7)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("document_type", "financial_year")
        ordering = ["document_type", "-financial_year"]

    def __str__(self) -> str:
        return f"{self.document_type}/{self.financial_year}/{self.last_number:04d}"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        CANCELLED = "cancelled", "Cancelled"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"

    campaign = models.ForeignKey(Campaign, related_name="invoices", on_delete=models.CASCADE)
    supplier_profile = models.ForeignKey(
        SupplierProfile,
        related_name="invoices",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    invoice_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    financial_year = models.CharField(max_length=7, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=255, blank=True)
    reverse_charge = models.BooleanField(default=False)
    currency_code = models.CharField(max_length=3, default="INR")

    supplier_legal_name = models.CharField(max_length=255, blank=True)
    supplier_trade_name = models.CharField(max_length=255, blank=True)
    supplier_gstin = models.CharField(max_length=15, blank=True)
    supplier_address_line_1 = models.CharField(max_length=255, blank=True)
    supplier_address_line_2 = models.CharField(max_length=255, blank=True)
    supplier_city = models.CharField(max_length=100, blank=True)
    supplier_state = models.CharField(max_length=100, blank=True)
    supplier_postal_code = models.CharField(max_length=20, blank=True)
    supplier_state_code = models.CharField(max_length=10, blank=True)
    supplier_country = models.CharField(max_length=100, blank=True, default="India")
    supplier_contact_email = models.EmailField(blank=True)
    supplier_contact_phone = models.CharField(max_length=30, blank=True)

    client_legal_name = models.CharField(max_length=255, blank=True)
    client_gstin = models.CharField(max_length=15, blank=True)
    client_billing_address_line_1 = models.CharField(max_length=255, blank=True)
    client_billing_address_line_2 = models.CharField(max_length=255, blank=True)
    client_billing_city = models.CharField(max_length=100, blank=True)
    client_billing_state = models.CharField(max_length=100, blank=True)
    client_billing_postal_code = models.CharField(max_length=20, blank=True)
    client_billing_state_code = models.CharField(max_length=10, blank=True)
    client_billing_country = models.CharField(max_length=100, blank=True, default="India")

    place_of_supply_state = models.CharField(max_length=100, blank=True)
    place_of_supply_state_code = models.CharField(max_length=10, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_value_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cess_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    pdf_file = models.FileField(upload_to="invoices/", blank=True, null=True, max_length=500)

    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="issued_invoices",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="cancelled_invoices",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(blank=True)

    irn = models.CharField(max_length=100, blank=True)
    acknowledgement_number = models.CharField(max_length=100, blank=True)
    acknowledgement_date = models.DateTimeField(null=True, blank=True)
    signed_qr_payload = models.TextField(blank=True)
    signed_qr_reference = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.invoice_number or f"Draft invoice #{self.pk}"


class CampaignEstimate(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="campaign_estimates",
        on_delete=models.CASCADE,
    )
    campaign = models.ForeignKey(
        Campaign,
        related_name="estimates",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    estimate_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    shared_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    approval_token_value = models.CharField(max_length=255, unique=True, editable=False, null=True, blank=True)
    approval_token_hash = models.CharField(max_length=64, unique=True, db_index=True, editable=False, null=True, blank=True)
    approval_token_prefix = models.CharField(max_length=16, editable=False, blank=True)
    approval_token_created_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_campaign_estimates",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def build_token_hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def issue_token(cls) -> str:
        return f"estimate_{secrets.token_urlsafe(24)}"

    @property
    def public_path(self) -> str | None:
        if not self.approval_token_value:
            return None
        return f"/estimate/{self.approval_token_value}"

    def has_public_token(self) -> bool:
        return bool(self.approval_token_value and self.approval_token_hash)

    def issue_public_token(self, *, force_new: bool = False) -> str:
        if self.has_public_token() and not force_new:
            return self.approval_token_value or ""

        raw_token = self.issue_token()
        self.approval_token_value = raw_token
        self.approval_token_hash = self.build_token_hash(raw_token)
        self.approval_token_prefix = raw_token[:12]
        self.approval_token_created_at = timezone.now()
        return raw_token

    def __str__(self) -> str:
        return self.estimate_number or self.title


class CampaignEstimateLine(TimeStampedModel):
    estimate = models.ForeignKey(CampaignEstimate, related_name="lines", on_delete=models.CASCADE)
    media_unit = models.ForeignKey(
        MediaUnit,
        related_name="estimate_lines",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.description


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    booking = models.ForeignKey(
        Booking,
        related_name="invoice_lines",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    line_number = models.PositiveIntegerField(default=1)
    site_name = models.CharField(max_length=255, blank=True)
    media_unit_label = models.CharField(max_length=100, blank=True)
    booking_start_date = models.DateField(null=True, blank=True)
    booking_end_date = models.DateField(null=True, blank=True)
    media_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    flex_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    installation_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_notes = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    item_description = models.CharField(max_length=255, blank=True)
    sac_code = models.CharField(max_length=20, blank=True)
    hsn_code = models.CharField(max_length=20, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_of_measure = models.CharField(max_length=30, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cess_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["line_number", "id"]

    def save(self, *args, **kwargs):
        if self.item_description and not self.description:
            self.description = self.item_description
        if self.description and not self.item_description:
            self.item_description = self.description
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.item_description or self.description or f"Invoice line {self.pk}"


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
        invoice_label = self.invoice.invoice_number or f"Draft #{self.invoice_id}"
        return f"{invoice_label} - {self.amount}"
