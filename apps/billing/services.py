import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.services import BaseService
from core.storage_backends import PrivateDocumentStorage, build_private_document_signed_url

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import RateCard

from .models import CampaignEstimate, CampaignEstimateLine, Invoice, InvoiceLine, InvoiceSequence, Payment, SupplierProfile
from .pdf import (
    build_invoice_pdf_storage_name,
    build_safe_invoice_pdf_name,
    render_invoice_pdf,
    render_invoice_pdf_fallback,
    render_invoice_pdf_last_resort,
)
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
logger = logging.getLogger(__name__)

DEFAULT_SAC_CODE = "998361"


def quantize_money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_booking_media_cost(booking: Booking) -> Decimal:
    media_cost = booking.agreed_media_cost or ZERO
    return quantize_money(media_cost if media_cost > ZERO else booking.booked_rate)


def get_default_supplier_profile() -> SupplierProfile | None:
    return SupplierProfile.objects.filter(is_active=True).order_by("id").first()


def get_company_profile():
    try:
        from apps.setup.models import CompanyProfile

        return CompanyProfile.objects.filter(singleton_key=1).first()
    except Exception:
        return None


def parse_configured_decimal(value) -> Decimal | None:
    if value in ("", None):
        return None
    try:
        amount = Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except Exception:
        return None
    return amount if amount > ZERO else None


def get_settings_gst_rate(*, sac_code: str = "") -> Decimal | None:
    mapping = getattr(settings, "BILLING_GST_RATE_BY_SAC", {}) or {}
    if isinstance(mapping, str):
        parsed = {}
        for pair in mapping.split(","):
            code, separator, rate = pair.partition(":")
            if separator and code.strip():
                parsed[code.strip()] = rate.strip()
        mapping = parsed

    if sac_code and isinstance(mapping, dict):
        mapped_rate = parse_configured_decimal(mapping.get(sac_code))
        if mapped_rate is not None:
            return mapped_rate
    return parse_configured_decimal(getattr(settings, "BILLING_DEFAULT_GST_RATE", ""))


def get_booking_rate_card_gst_rate(booking: Booking) -> Decimal | None:
    rate_card = (
        RateCard.objects.filter(
            unit=booking.media_unit,
            start_date__lte=booking.end_date,
            end_date__gte=booking.start_date,
            tax_percentage__gt=ZERO,
        )
        .order_by("-start_date", "-id")
        .first()
    )
    if not rate_card:
        return None
    return parse_configured_decimal(rate_card.tax_percentage)


def is_gst_registered_invoice(invoice: Invoice) -> bool:
    if invoice.supplier_gstin or getattr(invoice.supplier_profile, "gstin", ""):
        return True
    profile = get_company_profile()
    return bool(getattr(profile, "gstin", ""))


def populate_supplier_snapshot_from_company_profile(invoice: Invoice) -> None:
    profile = get_company_profile()
    if not profile:
        return
    invoice.supplier_legal_name = invoice.supplier_legal_name or profile.legal_name or profile.company_name
    invoice.supplier_trade_name = invoice.supplier_trade_name or profile.company_name
    invoice.supplier_gstin = invoice.supplier_gstin or profile.gstin
    invoice.supplier_state_code = invoice.supplier_state_code or profile.state_code
    if profile.address and not invoice.supplier_address_line_1:
        invoice.supplier_address_line_1 = profile.address
    invoice.supplier_contact_email = invoice.supplier_contact_email or profile.communication_email
    invoice.supplier_contact_phone = invoice.supplier_contact_phone or profile.phone


def populate_place_of_supply_from_bookings(invoice: Invoice) -> None:
    if invoice.place_of_supply_state or invoice.place_of_supply_state_code:
        return
    if invoice.client_billing_state or invoice.client_billing_state_code:
        invoice.place_of_supply_state = invoice.client_billing_state
        invoice.place_of_supply_state_code = invoice.client_billing_state_code
        return
    first_line = next(iter(invoice.lines.all().order_by("line_number", "id")), None)
    booking = getattr(first_line, "booking", None)
    site = getattr(getattr(booking, "media_unit", None), "site", None)
    if site and site.state:
        invoice.place_of_supply_state = site.state


def states_match(*, supplier_state_code: str = "", supplier_state: str = "", place_state_code: str = "", place_state: str = "") -> bool:
    supplier_state_code = (supplier_state_code or "").strip().upper()
    place_state_code = (place_state_code or "").strip().upper()
    if supplier_state_code and place_state_code:
        return supplier_state_code == place_state_code

    supplier_state = (supplier_state or "").strip().casefold()
    place_state = (place_state or "").strip().casefold()
    return bool(supplier_state and place_state and supplier_state == place_state)


def resolve_gst_rate_for_booking(booking: Booking, *, sac_code: str = "", requested_gst_rate: Decimal | None = None) -> Decimal | None:
    requested_rate = parse_configured_decimal(requested_gst_rate)
    if requested_rate is not None:
        return requested_rate

    rate_card_rate = get_booking_rate_card_gst_rate(booking)
    if rate_card_rate is not None:
        return rate_card_rate

    return get_settings_gst_rate(sac_code=sac_code)


def validate_gst_rate_available(invoice: Invoice, *, taxable_value: Decimal, gst_rate: Decimal, line) -> None:
    if taxable_value <= ZERO or not is_gst_registered_invoice(invoice):
        return
    if gst_rate > ZERO:
        return
    line_label = getattr(line, "line_number", "") or getattr(line, "pk", "")
    raise ValidationError(
        {
            "gst_rate": [
                f"GST rate is required for taxable invoice line {line_label}. Configure a rate card tax percentage, "
                "billing GST setting, or invoice line GST rate before issuing the invoice."
            ]
        }
    )


def build_booking_invoice_line_payload(booking: Booking, *, line_number: int) -> dict:
    media_cost = get_booking_media_cost(booking)
    flex_cost = quantize_money(booking.flex_cost or ZERO)
    installation_cost = quantize_money(booking.installation_cost or ZERO)
    other_cost = quantize_money(booking.other_cost or ZERO)
    line_total = quantize_money(media_cost + flex_cost + installation_cost + other_cost)
    site = booking.media_unit.site
    media_unit_label = booking.media_unit.unit_code

    return {
        "booking_id": booking.id,
        "line_number": line_number,
        "site_name": site.name,
        "media_unit_label": media_unit_label,
        "start_date": booking.start_date,
        "end_date": booking.end_date,
        "media_cost": media_cost,
        "flex_cost": flex_cost,
        "installation_cost": installation_cost,
        "other_cost": other_cost,
        "cost_notes": booking.cost_notes,
        "line_total": line_total,
        "description": f"Outdoor media display - {site.name} / {media_unit_label}",
    }


def get_confirmed_campaign_bookings(campaign: Campaign):
    return campaign.bookings.select_related("media_unit", "media_unit__site").filter(
        status=Booking.Status.CONFIRMED
    ).order_by("start_date", "media_unit__site__name", "media_unit__unit_code")


def build_campaign_invoice_preview(campaign: Campaign) -> dict:
    confirmed_bookings = list(get_confirmed_campaign_bookings(campaign))
    lines = [
        build_booking_invoice_line_payload(booking, line_number=index)
        for index, booking in enumerate(confirmed_bookings, start=1)
    ]
    subtotal = quantize_money(sum((line["line_total"] for line in lines), ZERO))
    existing_invoice = campaign.invoices.exclude(status=Invoice.Status.CANCELLED).order_by("-created_at").first()
    can_generate = not existing_invoice and campaign.start_date <= timezone.localdate() and bool(lines)

    message = ""
    if existing_invoice:
        message = "An invoice already exists for this campaign."
    elif campaign.start_date > timezone.localdate():
        message = "Invoice can be generated only from the campaign start date onward."
    elif not lines:
        message = "No confirmed bookings found for this campaign. Confirm bookings before generating an invoice."

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "campaign_code": campaign.code,
        "client_name": campaign.client.organization_name or campaign.client.get_full_name() or campaign.client.email,
        "start_date": campaign.start_date,
        "end_date": campaign.end_date,
        "confirmed_booking_count": len(lines),
        "subtotal": subtotal,
        "total_amount": subtotal,
        "existing_invoice_id": existing_invoice.id if existing_invoice else None,
        "existing_invoice_number": existing_invoice.invoice_number if existing_invoice else None,
        "can_generate": can_generate,
        "message": message,
        "lines": lines,
    }


def get_indian_financial_year(invoice_date: date) -> str:
    start_year = invoice_date.year if invoice_date.month >= 4 else invoice_date.year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


class PublicEstimateAccessError(Exception):
    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@transaction.atomic
def allocate_invoice_number(document_type: str, financial_year: str) -> str:
    sequence, _ = InvoiceSequence.objects.select_for_update().get_or_create(
        document_type=document_type,
        financial_year=financial_year,
        defaults={"last_number": 0},
    )
    while True:
        sequence.last_number += 1
        invoice_number = f"{document_type}/{financial_year}/{sequence.last_number:04d}"
        if not Invoice.objects.filter(invoice_number=invoice_number).exists():
            sequence.save(update_fields=["last_number", "updated_at"])
            return invoice_number


def calculate_invoice_totals(invoice: Invoice) -> Invoice:
    if invoice.supplier_profile:
        populate_supplier_snapshot(invoice, invoice.supplier_profile)
    else:
        populate_supplier_snapshot_from_company_profile(invoice)
    populate_place_of_supply_from_bookings(invoice)

    supplier_state_code = (invoice.supplier_state_code or "").strip().upper()
    place_of_supply_state_code = (invoice.place_of_supply_state_code or "").strip().upper()
    is_intra_state = states_match(
        supplier_state_code=supplier_state_code,
        supplier_state=invoice.supplier_state,
        place_state_code=place_of_supply_state_code,
        place_state=invoice.place_of_supply_state,
    )

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
        if gst_rate <= ZERO and getattr(line, "booking_id", None):
            resolved_rate = resolve_gst_rate_for_booking(line.booking, sac_code=line.sac_code or line.hsn_code)
            if resolved_rate is not None:
                gst_rate = resolved_rate
        validate_gst_rate_available(invoice, taxable_value=taxable_value, gst_rate=gst_rate, line=line)
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
        line.gst_rate = gst_rate
        line.cess_rate = cess_rate
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
                "gst_rate",
                "cess_rate",
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
        "client_legal_name": invoice.client_legal_name,
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
    if not getattr(invoice.campaign, "start_date", None):
        raise ValidationError({"campaign": ["Campaign start date is required before generating an invoice."]})
    if invoice.campaign.start_date > today:
        raise ValidationError(
            {"campaign": ["Invoice can be generated only from the campaign start date onward."]}
        )
    if not invoice.campaign.bookings.filter(status=Booking.Status.CONFIRMED).exists():
        raise ValidationError(
            {"campaign": ["No confirmed bookings found for this campaign. Confirm bookings before generating an invoice."]}
        )


def populate_invoice_issue_defaults(invoice: Invoice) -> None:
    if not invoice.invoice_date:
        invoice.invoice_date = invoice.issue_date or timezone.localdate()
    if not invoice.issue_date:
        invoice.issue_date = invoice.invoice_date
    if not invoice.due_date:
        invoice.due_date = invoice.invoice_date + timedelta(days=15)
    if not invoice.client_legal_name:
        client = getattr(invoice.campaign, "client", None)
        client_name = ""
        if client:
            client_name = (
                getattr(client, "organization_name", "")
                or getattr(client, "email", "")
                or f"Client #{client.pk}"
            )
        invoice.client_legal_name = client_name


@transaction.atomic
def issue_invoice(invoice: Invoice, actor) -> Invoice:
    invoice = (
        Invoice.objects.select_for_update()
        .prefetch_related("lines")
        .select_related("supplier_profile", "campaign__client")
        .get(pk=invoice.pk)
    )
    if invoice.status != Invoice.Status.DRAFT:
        raise ValidationError({"status": ["Only draft invoices can be issued."]})

    if invoice.supplier_profile:
        populate_supplier_snapshot(invoice, invoice.supplier_profile)
    populate_invoice_issue_defaults(invoice)

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

    pdf_bytes = render_invoice_pdf_safely(invoice)
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


def render_invoice_pdf_download(invoice: Invoice, actor=None) -> tuple[bytes, str]:
    try:
        if invoice.status == Invoice.Status.DRAFT:
            invoice = issue_invoice(invoice, actor=actor)
        invoice = (
            Invoice.objects.select_related("campaign", "supplier_profile", "issued_by")
            .prefetch_related("lines__booking__media_unit__site")
            .get(pk=invoice.pk)
        )
        validate_invoice_for_pdf(invoice)
        calculate_invoice_totals(invoice)
        filename = build_safe_invoice_pdf_name(invoice.invoice_number or f"invoice_{invoice.pk}")
        return render_invoice_pdf_safely(invoice), filename
    except ValidationError:
        raise
    except Exception:
        logger.exception("Invoice PDF download failed; using simplified fallback PDF.", extra={"invoice_id": invoice.pk})
        fallback_invoice = get_invoice_for_pdf_fallback(invoice)
        filename = build_safe_invoice_pdf_name(
            getattr(fallback_invoice, "invoice_number", "") or f"invoice_{invoice.pk}"
        )
        return render_invoice_pdf_fallback_safely(fallback_invoice), filename


def render_invoice_pdf_safely(invoice: Invoice) -> bytes:
    try:
        return render_invoice_pdf(invoice)
    except Exception:
        logger.exception("Invoice PDF renderer failed; using fallback PDF.", extra={"invoice_id": invoice.pk})
        return render_invoice_pdf_fallback_safely(invoice)


def render_invoice_pdf_fallback_safely(invoice: Invoice) -> bytes:
    try:
        return render_invoice_pdf_fallback(invoice)
    except Exception:
        logger.exception("Fallback invoice PDF renderer failed; using last-resort PDF.", extra={"invoice_id": invoice.pk})
        return render_invoice_pdf_last_resort(
            invoice_id=getattr(invoice, "pk", None),
            invoice_number=getattr(invoice, "invoice_number", None),
        )


def get_invoice_for_pdf_fallback(invoice: Invoice) -> Invoice:
    try:
        return (
            Invoice.objects.select_related("campaign", "supplier_profile", "issued_by")
            .prefetch_related("lines__booking__media_unit__site")
            .get(pk=invoice.pk)
        )
    except Exception:
        return invoice


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


def resolve_public_estimate(raw_token: str) -> CampaignEstimate:
    if not raw_token:
        raise PublicEstimateAccessError("invalid_token", "Estimate approval link is invalid.", 404)

    estimate = CampaignEstimate.objects.select_related("client", "campaign").prefetch_related("lines__media_unit__site").filter(
        approval_token_hash=CampaignEstimate.build_token_hash(raw_token)
    ).first()
    if not estimate:
        raise PublicEstimateAccessError("invalid_token", "Estimate approval link is invalid.", 404)

    if estimate.status == CampaignEstimate.Status.DRAFT:
        raise PublicEstimateAccessError("inactive_estimate", "This estimate has not been sent for approval yet.", 410)

    return estimate


def refresh_invoice_payment_status(invoice: Invoice) -> Invoice:
    if invoice.status == Invoice.Status.CANCELLED:
        return invoice
    if invoice.status == Invoice.Status.DRAFT:
        return invoice

    total_paid = invoice.payments.aggregate(total=models.Sum("amount")).get("total") or Decimal("0.00")
    payable_total = invoice.grand_total or invoice.total_amount
    next_status = invoice.status
    today = timezone.localdate()

    if payable_total > 0 and total_paid >= payable_total:
        next_status = Invoice.Status.PAID
    elif invoice.due_date and invoice.due_date < today:
        next_status = Invoice.Status.OVERDUE
    elif total_paid > 0:
        next_status = Invoice.Status.PARTIALLY_PAID
    else:
        next_status = Invoice.Status.ISSUED

    if next_status != invoice.status:
        invoice.status = next_status
        invoice.save(update_fields=["status", "updated_at"])
    return invoice


class CampaignEstimateService(BaseService):
    repository_class = CampaignEstimateRepository

    def _assert_editable(self, instance: CampaignEstimate):
        if instance.status == CampaignEstimate.Status.APPROVED:
            raise ValidationError({"status": ["Approved estimates are locked and cannot be edited."]})

    def create(self, actor=None, **validated_data):
        estimate = super().create(actor=actor, created_by=actor, **validated_data)
        estimate.estimate_number = f"EST/{estimate.created_at:%Y-%y}/{estimate.id:04d}"
        estimate.save(update_fields=["estimate_number", "updated_at"])
        return estimate

    def update(self, instance, actor=None, **validated_data):
        self._assert_editable(instance)
        return super().update(instance, actor=actor, **validated_data)

    def share(self, instance, actor=None):
        if instance.status not in {CampaignEstimate.Status.DRAFT, CampaignEstimate.Status.REJECTED, CampaignEstimate.Status.SENT}:
            raise ValidationError({"status": ["Only draft or rejected estimates can be sent for approval."]})
        instance.issue_public_token(force_new=instance.status == CampaignEstimate.Status.REJECTED)
        instance.status = CampaignEstimate.Status.SENT
        instance.shared_at = instance.shared_at or timezone.now()
        instance.save(
            update_fields=[
                "status",
                "shared_at",
                "approval_token_value",
                "approval_token_hash",
                "approval_token_prefix",
                "approval_token_created_at",
                "updated_at",
            ]
        )
        return instance

    def approve(self, instance, actor=None, comment=""):
        if instance.status != CampaignEstimate.Status.SENT:
            raise ValidationError({"status": ["Only sent estimates can be approved."]})
        instance.status = CampaignEstimate.Status.APPROVED
        instance.approved_at = instance.approved_at or timezone.now()
        instance.client_response_comment = comment or instance.client_response_comment
        instance.save(update_fields=["status", "approved_at", "client_response_comment", "updated_at"])
        return instance

    def reject(self, instance, actor=None, comment=""):
        if instance.status != CampaignEstimate.Status.SENT:
            raise ValidationError({"status": ["Only sent estimates can be rejected."]})
        instance.status = CampaignEstimate.Status.REJECTED
        instance.rejected_at = timezone.now()
        instance.client_response_comment = comment or instance.client_response_comment
        instance.save(update_fields=["status", "rejected_at", "client_response_comment", "updated_at"])
        return instance

    def resolve_public(self, raw_token: str) -> CampaignEstimate:
        return resolve_public_estimate(raw_token)

    def respond_public(self, raw_token: str, *, decision: str, comment: str = "") -> CampaignEstimate:
        estimate = self.resolve_public(raw_token)
        if decision == "approve":
            return self.approve(estimate, comment=comment)
        if decision == "reject":
            return self.reject(estimate, comment=comment)
        raise ValidationError({"decision": ["Unsupported estimate decision."]})


class CampaignEstimateLineService(BaseService):
    repository_class = CampaignEstimateLineRepository

    def _assert_estimate_editable(self, estimate: CampaignEstimate):
        if estimate.status == CampaignEstimate.Status.APPROVED:
            raise ValidationError({"estimate": ["Approved estimates are locked and cannot be edited."]})

    def create(self, actor=None, **validated_data):
        self._assert_estimate_editable(validated_data["estimate"])
        line = super().create(actor=actor, **validated_data)
        calculate_estimate_totals(line.estimate)
        return line

    def update(self, instance, actor=None, **validated_data):
        self._assert_estimate_editable(instance.estimate)
        line = super().update(instance, actor=actor, **validated_data)
        calculate_estimate_totals(line.estimate)
        return line

    def delete(self, instance, actor=None):
        estimate = instance.estimate
        self._assert_estimate_editable(estimate)
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
        estimate_queryset = CampaignEstimate.objects.all()
        if user and getattr(user, "role", None) == "client":
            estimate_queryset = estimate_queryset.filter(client=user)

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
        summary["total_estimated"] = estimate_queryset.aggregate(
            total_estimated=Coalesce(Sum("total_amount"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD)
        )["total_estimated"]
        summary["total_approved_estimates"] = estimate_queryset.aggregate(
            total_approved_estimates=Coalesce(
                Sum("total_amount", filter=Q(status=CampaignEstimate.Status.APPROVED)),
                Decimal("0.00"),
                output_field=SUMMARY_DECIMAL_FIELD,
            )
        )["total_approved_estimates"]
        payment_summary = payment_queryset.aggregate(
            payment_count=Count("id"),
            total_paid=Coalesce(Sum("amount"), Decimal("0.00"), output_field=SUMMARY_DECIMAL_FIELD),
        )
        summary.update(payment_summary)
        summary["outstanding_amount"] = max(summary["total_invoiced"] - summary["total_paid"], Decimal("0.00"))
        summary["total_collected"] = summary["total_paid"]
        summary["outstanding_balance"] = summary["outstanding_amount"]
        return summary

    def get_queryset(self, user=None):
        queryset = super().get_queryset(user=user)
        for invoice in queryset.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]):
            refresh_invoice_payment_status(invoice)
        return queryset

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

    def render_pdf_download(self, instance, actor=None):
        return render_invoice_pdf_download(instance, actor=actor)

    @transaction.atomic
    def generate_from_bookings(self, *, actor=None, campaign, supplier_profile=None, invoice_date=None, due_date=None, payment_terms="", gst_rate=None, sac_code=DEFAULT_SAC_CODE):
        invoice_date = invoice_date or timezone.localdate()
        due_date = due_date or invoice_date + timedelta(days=15)
        existing_invoice = campaign.invoices.exclude(status=Invoice.Status.CANCELLED).order_by("-created_at").first()
        if existing_invoice:
            raise ValidationError({"campaign": ["An invoice already exists for this campaign."]})

        supplier_profile = supplier_profile or get_default_supplier_profile()

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

        confirmed_bookings = list(get_confirmed_campaign_bookings(campaign))
        if not confirmed_bookings:
            raise ValidationError(
                {"campaign": ["No confirmed bookings found for this campaign. Confirm bookings before generating an invoice."]}
            )

        invoice.save()
        for index, booking in enumerate(confirmed_bookings, start=1):
            line_payload = build_booking_invoice_line_payload(booking, line_number=index)
            line_gst_rate = resolve_gst_rate_for_booking(booking, sac_code=sac_code, requested_gst_rate=gst_rate)
            if is_gst_registered_invoice(invoice) and line_gst_rate is None:
                raise ValidationError(
                    {
                        "gst_rate": [
                            "GST rate is required for taxable booking invoice lines. Configure a media rate card tax "
                            "percentage, billing GST setting, or pass an invoice GST rate."
                        ]
                    }
                )
            InvoiceLine.objects.create(
                invoice=invoice,
                booking=booking,
                line_number=index,
                site_name=line_payload["site_name"],
                media_unit_label=line_payload["media_unit_label"],
                booking_start_date=line_payload["start_date"],
                booking_end_date=line_payload["end_date"],
                media_cost=line_payload["media_cost"],
                flex_cost=line_payload["flex_cost"],
                installation_cost=line_payload["installation_cost"],
                other_cost=line_payload["other_cost"],
                cost_notes=line_payload["cost_notes"],
                item_description=line_payload["description"],
                description=line_payload["description"],
                sac_code=sac_code,
                quantity=Decimal("1.00"),
                unit_of_measure="booking",
                unit_price=line_payload["line_total"],
                gst_rate=line_gst_rate or ZERO,
            )
        calculate_invoice_totals(invoice)
        invoice.save()
        return invoice

    def preview_for_campaign(self, *, campaign):
        return build_campaign_invoice_preview(campaign)

    @transaction.atomic
    def generate_for_campaign(self, *, actor=None, campaign):
        return self.generate_from_bookings(
            actor=actor,
            campaign=campaign,
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=15),
            payment_terms="Net 15",
        )


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
        refresh_invoice_payment_status(invoice)
