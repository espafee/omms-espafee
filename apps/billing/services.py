from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.services import BaseService
from core.storage_backends import PrivateDocumentStorage, build_private_document_signed_url

from apps.bookings.models import Booking

from .models import CampaignEstimate, CampaignEstimateLine, Invoice, InvoiceLine, InvoiceSequence, Payment, SupplierProfile
from .pdf import build_invoice_pdf_storage_name, render_invoice_pdf
from .repositories import (
    CampaignEstimateLineRepository,
    CampaignEstimateRepository,
    InvoiceLineRepository,
    InvoiceRepository,
    PaymentRepository,
    SupplierProfileRepository,
)

SUMMARY_DECIMAL_FIELD = DecimalField(max_digits=14, decimal_places=2)
MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def quantize_money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_indian_financial_year(invoice_date: date) -> str:
    start_year = invoice_date.year if invoice_date.month >= 4 else invoice_date.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


@transaction.atomic
def allocate_invoice_number(document_type: str, financial_year: str) -> str:
    sequence, _ = InvoiceSequence.objects.select_for_update().get_or_create(
        document_type=document_type,
        financial_year=financial_year,
        defaults={"last_number": 0},
    )
    sequence.last_number += 1
    sequence.save(update_fields=["last_number", "updated_at"])
    return f"{document_type}/{financial_year}/{sequence.last_number:04d}"


def calculate_invoice_totals(invoice: Invoice) -> Invoice:
    if invoice.supplier_profile:
        populate_supplier_snapshot(invoice, invoice.supplier_profile)

    supplier_state_code = (invoice.supplier_state_code or "").strip().upper()
    place_of_supply_state_code = (invoice.place_of_supply_state_code or "").strip().upper()
    is_intra_state = bool(supplier_state_code and supplier_state_code == place_of_supply_state_code)

    taxable_total = ZERO
    discount_total = ZERO
    cgst_total = ZERO
    sgst_total = ZERO
    igst_total = ZERO
    cess_total = ZERO

    lines = list(invoice.lines.all().order_by("line_number", "id"))
    for index, line in enumerate(lines, start=1):
        quantity = quantize_money(line.quantity or ZERO)
        unit_price = quantize_money(line.unit_price or ZERO)
        gross_value = quantize_money(quantity * unit_price)
        discount_amount = quantize_money(line.discount_amount or ZERO)
        taxable_value = quantize_money(gross_value - discount_amount)
        if taxable_value < ZERO:
            taxable_value = ZERO

        gst_rate = quantize_money(line.gst_rate or ZERO)
        cess_rate = quantize_money(line.cess_rate or ZERO)

        cgst_rate = ZERO
        sgst_rate = ZERO
        igst_rate = ZERO

        if is_intra_state:
            cgst_rate = quantize_money(gst_rate / Decimal("2")) if gst_rate else ZERO
            sgst_rate = quantize_money(gst_rate / Decimal("2")) if gst_rate else ZERO
        else:
            igst_rate = gst_rate

        cgst_amount = quantize_money((taxable_value * cgst_rate) / Decimal("100"))
        sgst_amount = quantize_money((taxable_value * sgst_rate) / Decimal("100"))
        igst_amount = quantize_money((taxable_value * igst_rate) / Decimal("100"))
        cess_amount = quantize_money((taxable_value * cess_rate) / Decimal("100"))
        line_total = quantize_money(taxable_value + cgst_amount + sgst_amount + igst_amount + cess_amount)

        line.line_number = index
        line.gross_value = gross_value
        line.taxable_value = taxable_value
        line.cgst_rate = cgst_rate
        line.cgst_amount = cgst_amount
        line.sgst_rate = sgst_rate
        line.sgst_amount = sgst_amount
        line.igst_rate = igst_rate
        line.igst_amount = igst_amount
        line.cess_amount = cess_amount
        line.line_total = line_total
        if line.item_description and not line.description:
            line.description = line.item_description
        if line.description and not line.item_description:
            line.item_description = line.description
        line.save(
            update_fields=[
                "line_number",
                "gross_value",
                "taxable_value",
                "cgst_rate",
                "cgst_amount",
                "sgst_rate",
                "sgst_amount",
                "igst_rate",
                "igst_amount",
                "cess_amount",
                "line_total",
                "description",
                "item_description",
                "updated_at",
            ]
        )

        taxable_total += taxable_value
        discount_total += discount_amount
        cgst_total += cgst_amount
        sgst_total += sgst_amount
        igst_total += igst_amount
        cess_total += cess_amount

    total_tax = quantize_money(cgst_total + sgst_total + igst_total + cess_total)
    grand_total = quantize_money(taxable_total + total_tax)

    invoice.taxable_value_total = quantize_money(taxable_total)
    invoice.discount_total = quantize_money(discount_total)
    invoice.cgst_total = quantize_money(cgst_total)
    invoice.sgst_total = quantize_money(sgst_total)
    invoice.igst_total = quantize_money(igst_total)
    invoice.cess_total = quantize_money(cess_total)
    invoice.total_tax = total_tax
    invoice.grand_total = grand_total
    invoice.subtotal = invoice.taxable_value_total
    invoice.tax_amount = total_tax
    invoice.total_amount = grand_total
    if invoice.invoice_date:
        invoice.issue_date = invoice.invoice_date
    return invoice


def populate_supplier_snapshot(invoice: Invoice, supplier_profile: SupplierProfile) -> None:
    invoice.supplier_legal_name = invoice.supplier_legal_name or supplier_profile.legal_name
    invoice.supplier_trade_name = invoice.supplier_trade_name or supplier_profile.trade_name
    invoice.supplier_gstin = invoice.supplier_gstin or supplier_profile.gstin
    invoice.supplier_address_line_1 = invoice.supplier_address_line_1 or supplier_profile.address_line_1
    invoice.supplier_address_line_2 = invoice.supplier_address_line_2 or supplier_profile.address_line_2
    invoice.supplier_city = invoice.supplier_city or supplier_profile.city
    invoice.supplier_state = invoice.supplier_state or supplier_profile.state
    invoice.supplier_postal_code = invoice.supplier_postal_code or supplier_profile.postal_code
    invoice.supplier_state_code = invoice.supplier_state_code or supplier_profile.state_code
    invoice.supplier_country = invoice.supplier_country or supplier_profile.country
    invoice.supplier_contact_email = invoice.supplier_contact_email or supplier_profile.contact_email
    invoice.supplier_contact_phone = invoice.supplier_contact_phone or supplier_profile.contact_phone


def validate_invoice_for_issue(invoice: Invoice) -> None:
    required_fields = {
        "supplier_legal_name": invoice.supplier_legal_name,
        "supplier_gstin": invoice.supplier_gstin,
        "supplier_address_line_1": invoice.supplier_address_line_1,
        "supplier_city": invoice.supplier_city,
        "supplier_state": invoice.supplier_state,
        "supplier_postal_code": invoice.supplier_postal_code,
        "supplier_state_code": invoice.supplier_state_code,
        "client_legal_name": invoice.client_legal_name,
        "client_billing_address_line_1": invoice.client_billing_address_line_1,
        "client_billing_city": invoice.client_billing_city,
        "client_billing_state": invoice.client_billing_state,
        "client_billing_postal_code": invoice.client_billing_postal_code,
        "place_of_supply_state": invoice.place_of_supply_state,
        "place_of_supply_state_code": invoice.place_of_supply_state_code,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
    }
    missing = [field for field, value in required_fields.items() if value in ("", None)]
    if missing:
        raise ValidationError({field: ["This field is required before issuing the invoice."] for field in missing})
    if not invoice.lines.exists():
        raise ValidationError({"lines": ["Add at least one invoice line before issuing the invoice."]})
    validate_invoice_campaign_ready(invoice)


def validate_invoice_campaign_ready(invoice: Invoice) -> None:
    today = timezone.localdate()
    if invoice.campaign.start_date > today:
        raise ValidationError(
            {"campaign": ["Invoice can be generated only from the campaign start date onward."]}
        )
    if not invoice.campaign.bookings.filter(status=Booking.Status.CONFIRMED).exists():
        raise ValidationError({"campaign": ["Invoice requires at least one confirmed booking."]})


@transaction.atomic
def issue_invoice(invoice: Invoice, actor) -> Invoice:
    invoice = Invoice.objects.select_for_update().prefetch_related("lines").select_related("supplier_profile").get(pk=invoice.pk)
    if invoice.status != Invoice.Status.DRAFT:
        raise ValidationError({"status": ["Only draft invoices can be issued."]})

    if invoice.supplier_profile:
        populate_supplier_snapshot(invoice, invoice.supplier_profile)

    validate_invoice_for_issue(invoice)
    invoice.financial_year = invoice.financial_year or get_indian_financial_year(invoice.invoice_date)
    invoice.invoice_number = allocate_invoice_number(InvoiceSequence.DocumentType.INVOICE, invoice.financial_year)

    calculate_invoice_totals(invoice)
    invoice.status = Invoice.Status.ISSUED
    invoice.issued_at = timezone.now()
    invoice.issued_by = actor
    invoice.save()
    return invoice


def validate_invoice_for_pdf(invoice: Invoice) -> None:
    allowed_statuses = {
        Invoice.Status.ISSUED,
        Invoice.Status.PARTIALLY_PAID,
        Invoice.Status.PAID,
        Invoice.Status.OVERDUE,
    }
    if invoice.status not in allowed_statuses:
        raise ValidationError({"status": ["Only issued invoices can generate an official PDF."]})
    if not invoice.invoice_number:
        raise ValidationError({"invoice_number": ["Issue the invoice before generating a PDF."]})


@transaction.atomic
def generate_invoice_pdf(invoice: Invoice, actor=None) -> Invoice:
    invoice = (
        Invoice.objects.select_for_update()
        .select_related("campaign", "supplier_profile", "issued_by")
        .prefetch_related("lines__booking__media_unit__site")
        .get(pk=invoice.pk)
    )
    validate_invoice_for_pdf(invoice)
    calculate_invoice_totals(invoice)

    pdf_bytes = render_invoice_pdf(invoice)
    storage = PrivateDocumentStorage()
    target_name = build_invoice_pdf_storage_name(invoice)

    if invoice.pdf_file and invoice.pdf_file.name:
        try:
            storage.delete(invoice.pdf_file.name)
        except Exception:
            pass
    if storage.exists(target_name):
        storage.delete(target_name)

    stored_name = storage.save(target_name, ContentFile(pdf_bytes))
    invoice.pdf_file.name = stored_name
    invoice.save(
        update_fields=[
            "pdf_file",
            "subtotal",
            "tax_amount",
            "total_amount",
            "taxable_value_total",
            "discount_total",
            "cgst_total",
            "sgst_total",
            "igst_total",
            "cess_total",
            "total_tax",
            "grand_total",
            "updated_at",
        ]
    )
    return invoice


def get_invoice_pdf_link(invoice: Invoice, *, expiry_seconds: int | None = None) -> str:
    if not invoice.pdf_file or not invoice.pdf_file.name:
        raise ValidationError({"pdf_file": ["Generate the invoice PDF before requesting a download link."]})
    return build_private_document_signed_url(
        invoice.pdf_file.name,
        expiry_seconds=expiry_seconds,
        storage=PrivateDocumentStorage(),
    )


class SupplierProfileService(BaseService):
    repository_class = SupplierProfileRepository


def calculate_estimate_totals(estimate: CampaignEstimate) -> CampaignEstimate:
    subtotal = ZERO
    tax_amount = ZERO
    for line in estimate.lines.all():
        taxable = quantize_money((line.quantity or ZERO) * (line.unit_rate or ZERO))
        tax = quantize_money((taxable * (line.tax_rate or ZERO)) / Decimal("100"))
        total = quantize_money(taxable + tax)
        line.taxable_amount = taxable
        line.tax_amount = tax
        line.total_amount = total
        line.save(update_fields=["taxable_amount", "tax_amount", "total_amount", "updated_at"])
        subtotal += taxable
        tax_amount += tax
    estimate.subtotal = quantize_money(subtotal)
    estimate.tax_amount = quantize_money(tax_amount)
    estimate.total_amount = quantize_money(subtotal + tax_amount)
    estimate.save(update_fields=["subtotal", "tax_amount", "total_amount", "updated_at"])
    return estimate


class CampaignEstimateService(BaseService):
    repository_class = CampaignEstimateRepository

    def create(self, actor=None, **validated_data):
        estimate = super().create(actor=actor, created_by=actor, **validated_data)
        estimate.estimate_number = f"EST/{estimate.created_at:%Y-%y}/{estimate.id:04d}"
        estimate.save(update_fields=["estimate_number", "updated_at"])
        return estimate

    def share(self, instance, actor=None):
        if instance.status not in {CampaignEstimate.Status.DRAFT, CampaignEstimate.Status.SHARED}:
            raise ValidationError({"status": ["Only draft estimates can be shared."]})
        instance.status = CampaignEstimate.Status.SHARED
        instance.shared_at = instance.shared_at or timezone.now()
        instance.save(update_fields=["status", "shared_at", "updated_at"])
        return instance

    def approve(self, instance, actor=None):
        if instance.status not in {CampaignEstimate.Status.SHARED, CampaignEstimate.Status.APPROVED}:
            raise ValidationError({"status": ["Only shared estimates can be approved."]})
        instance.status = CampaignEstimate.Status.APPROVED
        instance.approved_at = instance.approved_at or timezone.now()
        instance.save(update_fields=["status", "approved_at", "updated_at"])
        return instance

    def finalize(self, instance, actor=None):
        if instance.status != CampaignEstimate.Status.APPROVED:
            raise ValidationError({"status": ["Only approved estimates can be finalized."]})
        instance.status = CampaignEstimate.Status.FINALIZED
        instance.finalized_at = timezone.now()
        instance.save(update_fields=["status", "finalized_at", "updated_at"])
        return instance


class CampaignEstimateLineService(BaseService):
    repository_class = CampaignEstimateLineRepository

    def create(self, actor=None, **validated_data):
        line = super().create(actor=actor, **validated_data)
        calculate_estimate_totals(line.estimate)
        return line

    def update(self, instance, actor=None, **validated_data):
        line = super().update(instance, actor=actor, **validated_data)
        calculate_estimate_totals(line.estimate)
        return line

    def delete(self, instance, actor=None):
        estimate = instance.estimate
        super().delete(instance, actor=actor)
        calculate_estimate_totals(estimate)


class InvoiceService(BaseService):
    repository_class = InvoiceRepository

    LOCKED_STATUSES = {
        Invoice.Status.ISSUED,
        Invoice.Status.PARTIALLY_PAID,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
        Invoice.Status.OVERDUE,
    }

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

    @transaction.atomic
    def create(self, actor=None, **validated_data):
        validated_data.pop("invoice_number", None)
        validated_data["status"] = Invoice.Status.DRAFT
        if not validated_data.get("invoice_date") and validated_data.get("issue_date"):
            validated_data["invoice_date"] = validated_data["issue_date"]
        if not validated_data.get("issue_date") and validated_data.get("invoice_date"):
            validated_data["issue_date"] = validated_data["invoice_date"]
        invoice = Invoice(**validated_data)
        validate_invoice_campaign_ready(invoice)
        return super().create(actor=actor, **validated_data)

    @transaction.atomic
    def update(self, instance, actor=None, **validated_data):
        if instance.status in self.LOCKED_STATUSES:
            raise ValidationError({"status": ["Issued, paid, cancelled, or overdue invoices cannot be edited directly."]})
        if "invoice_date" in validated_data and "issue_date" not in validated_data:
            validated_data["issue_date"] = validated_data["invoice_date"]
        if "issue_date" in validated_data and "invoice_date" not in validated_data:
            validated_data["invoice_date"] = validated_data["issue_date"]
        return super().update(instance, actor=actor, **validated_data)

    @transaction.atomic
    def issue(self, instance, actor=None):
        return issue_invoice(instance, actor=actor)

    @transaction.atomic
    def generate_pdf(self, instance, actor=None):
        return generate_invoice_pdf(instance, actor=actor)

    def get_pdf_link(self, instance, *, expiry_seconds: int | None = None):
        return get_invoice_pdf_link(instance, expiry_seconds=expiry_seconds)

    @transaction.atomic
    def generate_from_bookings(self, *, actor=None, campaign, supplier_profile=None, invoice_date=None, due_date=None, payment_terms="", gst_rate=Decimal("18.00"), sac_code="998361"):
        invoice_date = invoice_date or timezone.localdate()
        invoice = Invoice(
            campaign=campaign,
            supplier_profile=supplier_profile,
            invoice_date=invoice_date,
            issue_date=invoice_date,
            due_date=due_date,
            payment_terms=payment_terms,
            client_legal_name=campaign.client.organization_name or campaign.client.get_full_name() or campaign.client.email,
        )
        validate_invoice_campaign_ready(invoice)
        invoice.save()

        confirmed_bookings = campaign.bookings.select_related("media_unit", "media_unit__site").filter(
            status=Booking.Status.CONFIRMED
        )
        for index, booking in enumerate(confirmed_bookings, start=1):
            site = booking.media_unit.site
            InvoiceLine.objects.create(
                invoice=invoice,
                booking=booking,
                line_number=index,
                item_description=f"Outdoor media display - {site.name} / {booking.media_unit.unit_code}",
                description=f"Outdoor media display - {site.name} / {booking.media_unit.unit_code}",
                sac_code=sac_code,
                quantity=Decimal("1.00"),
                unit_of_measure="booking",
                unit_price=booking.booked_rate,
                gst_rate=gst_rate,
            )
        calculate_invoice_totals(invoice)
        invoice.save()
        return invoice


class InvoiceLineService(BaseService):
    repository_class = InvoiceLineRepository

    LOCKED_STATUSES = {
        Invoice.Status.ISSUED,
        Invoice.Status.PARTIALLY_PAID,
        Invoice.Status.PAID,
        Invoice.Status.CANCELLED,
        Invoice.Status.OVERDUE,
    }

    def _assert_invoice_editable(self, invoice: Invoice):
        if invoice.status in self.LOCKED_STATUSES:
            raise ValidationError({"invoice": ["Invoice lines cannot be modified after the invoice is issued."]})

    @transaction.atomic
    def create(self, actor=None, **validated_data):
        invoice = validated_data["invoice"]
        self._assert_invoice_editable(invoice)
        return super().create(actor=actor, **validated_data)

    @transaction.atomic
    def update(self, instance, actor=None, **validated_data):
        self._assert_invoice_editable(instance.invoice)
        return super().update(instance, actor=actor, **validated_data)

    @transaction.atomic
    def delete(self, instance, actor=None):
        self._assert_invoice_editable(instance.invoice)
        return super().delete(instance, actor=actor)


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
        payable_total = invoice.grand_total or invoice.total_amount
        if invoice.status == Invoice.Status.CANCELLED:
            return
        if total_paid <= 0:
            return
        if total_paid >= payable_total:
            invoice.status = Invoice.Status.PAID
        else:
            invoice.status = Invoice.Status.PARTIALLY_PAID
        invoice.save(update_fields=["status", "updated_at"])
