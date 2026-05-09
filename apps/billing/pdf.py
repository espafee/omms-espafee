from __future__ import annotations

import io
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen.canvas import Canvas

from .models import Invoice

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def quantize_money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def format_money(value: Decimal | int | str) -> str:
    return f"{quantize_money(value):,.2f}"


def build_safe_invoice_pdf_name(invoice_number: str) -> str:
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", invoice_number.strip()).strip("_")
    return f"{safe_number or 'invoice'}.pdf"


def build_invoice_pdf_storage_name(invoice: Invoice) -> str:
    financial_year = invoice.financial_year or "draft"
    filename = build_safe_invoice_pdf_name(invoice.invoice_number or f"invoice_{invoice.pk}")
    return f"invoices/{financial_year}/{filename}"


def _pdf_text(value, default: str = "-") -> str:
    if value in ("", None):
        value = default
    return escape(str(value), quote=False)


def _pdf_bold(value, default: str = "-") -> str:
    return f"<b>{_pdf_text(value, default=default)}</b>"


def _pdf_lines(parts) -> str:
    return "<br/>".join(str(part) for part in parts if part not in ("", None))


def _pdf_text_lines(parts, default: str = "-") -> str:
    lines = [_pdf_text(part, default="") for part in parts if part not in ("", None)]
    return "<br/>".join(line for line in lines if line) or _pdf_text(default, default="")


def _pdf_multiline(value, default: str = "-") -> str:
    if value in ("", None):
        return _pdf_text(default)
    lines = [_pdf_text(line, default="") for line in str(value).splitlines()]
    return "<br/>".join(line for line in lines if line) or _pdf_text(default)


class UncompressedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("pageCompression", 0)
        super().__init__(*args, **kwargs)


def render_invoice_pdf(invoice: Invoice) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="InvoiceTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=10.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallRight",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=10.5,
            alignment=TA_RIGHT,
        )
    )

    story: list = [Paragraph("Tax Invoice", styles["InvoiceTitle"])]

    seller_name = invoice.supplier_trade_name or invoice.supplier_legal_name or "-"
    seller_address = ", ".join(
        filter(
            None,
            [
                invoice.supplier_address_line_1,
                invoice.supplier_address_line_2,
                invoice.supplier_city,
                invoice.supplier_state,
                invoice.supplier_postal_code,
            ],
        )
    )
    seller_contact = _pdf_text_lines(
        [
            f"Phone No.: {invoice.supplier_contact_phone}" if invoice.supplier_contact_phone else "",
            f"Email ID: {invoice.supplier_contact_email}" if invoice.supplier_contact_email else "",
            f"GSTIN: {invoice.supplier_gstin}" if invoice.supplier_gstin else "",
            f"State: {invoice.supplier_state}" if invoice.supplier_state else "",
        ],
        default="",
    )

    client_address = ", ".join(
        filter(
            None,
            [
                invoice.client_billing_address_line_1,
                invoice.client_billing_address_line_2,
                invoice.client_billing_city,
                invoice.client_billing_state,
                invoice.client_billing_postal_code,
            ],
        )
    )
    service_location = _build_service_location(invoice)
    campaign_description = _build_campaign_description(invoice)
    campaign_period = _build_campaign_period(invoice)

    header_table = Table(
        [
            [
                Paragraph("<b>Seller / Supplier</b>", styles["SectionLabel"]),
                Paragraph("<b>Invoice Details</b>", styles["SectionLabel"]),
            ],
            [
                Paragraph(
                    _pdf_lines(
                        [
                            _pdf_bold(seller_name),
                            _pdf_text(seller_address, default=""),
                            seller_contact,
                        ]
                    ),
                    styles["Cell"],
                ),
                Paragraph(
                    _pdf_lines(
                        [
                            f"Invoice No.: <b>{_pdf_text(invoice.invoice_number)}</b>",
                            f"Date: {invoice.invoice_date:%d-%m-%Y}" if invoice.invoice_date else "Date: -",
                            f"Client GSTIN No.: {_pdf_text(invoice.client_gstin)}",
                        ]
                    ),
                    styles["Cell"],
                ),
            ],
            [
                Paragraph("<b>Bill To</b>", styles["SectionLabel"]),
                Paragraph("<b>Shipping To / Service Location</b>", styles["SectionLabel"]),
            ],
            [
                Paragraph(
                    _pdf_lines(
                        [
                            _pdf_bold(invoice.client_legal_name),
                            _pdf_text(client_address),
                        ]
                    ),
                    styles["Cell"],
                ),
                Paragraph(_pdf_multiline(service_location), styles["Cell"]),
            ],
            [
                Paragraph("<b>Campaign / Service Description</b>", styles["SectionLabel"]),
                Paragraph("<b>Period</b>", styles["SectionLabel"]),
            ],
            [
                Paragraph(_pdf_text(campaign_description), styles["Cell"]),
                Paragraph(_pdf_text(campaign_period), styles["Cell"]),
            ],
        ],
        colWidths=[95 * mm, 85 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f9fafb")),
                ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#f9fafb")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([header_table, Spacer(1, 6)])

    line_rows = [
        [
            Paragraph("<b>S.No.</b>", styles["CellBold"]),
            Paragraph("<b>Item name</b>", styles["CellBold"]),
            Paragraph("<b>Qty/Size</b>", styles["CellBold"]),
            Paragraph("<b>Unit</b>", styles["CellBold"]),
            Paragraph("<b>Price/Unit</b>", styles["CellBold"]),
            Paragraph("<b>HSN/SAC</b>", styles["CellBold"]),
            Paragraph("<b>CGST Rate</b>", styles["CellBold"]),
            Paragraph("<b>CGST Amt.</b>", styles["CellBold"]),
            Paragraph("<b>SGST Rate</b>", styles["CellBold"]),
            Paragraph("<b>SGST Amt.</b>", styles["CellBold"]),
            Paragraph("<b>IGST Rate/Amt</b>", styles["CellBold"]),
            Paragraph("<b>Amount</b>", styles["CellBold"]),
        ]
    ]

    for index, line in enumerate(invoice.lines.all().order_by("line_number", "id"), start=1):
        qty_label = _build_qty_size_label(line.quantity, getattr(line.booking, "media_unit", None))
        igst_display = "-" if not line.igst_rate and not line.igst_amount else f"{line.igst_rate}% / {format_money(line.igst_amount)}"
        line_rows.append(
            [
                Paragraph(str(index), styles["Cell"]),
                Paragraph(_pdf_text(line.item_description or line.description), styles["Cell"]),
                Paragraph(_pdf_text(qty_label), styles["Cell"]),
                Paragraph(_pdf_text(line.unit_of_measure), styles["Cell"]),
                Paragraph(format_money(line.unit_price), styles["SmallRight"]),
                Paragraph(_pdf_text(line.hsn_code or line.sac_code), styles["Cell"]),
                Paragraph(f"{line.cgst_rate}%", styles["SmallRight"]),
                Paragraph(format_money(line.cgst_amount), styles["SmallRight"]),
                Paragraph(f"{line.sgst_rate}%", styles["SmallRight"]),
                Paragraph(format_money(line.sgst_amount), styles["SmallRight"]),
                Paragraph(igst_display, styles["SmallRight"]),
                Paragraph(format_money(line.line_total), styles["SmallRight"]),
            ]
        )

    line_table = Table(
        line_rows,
        repeatRows=1,
        colWidths=[8 * mm, 32 * mm, 14 * mm, 10 * mm, 14 * mm, 14 * mm, 12 * mm, 14 * mm, 12 * mm, 14 * mm, 16 * mm, 18 * mm],
    )
    line_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([line_table, Spacer(1, 6)])

    tax_summary = _build_tax_summary_rows(invoice)
    tax_summary_table = Table(
        [
            [
                Paragraph("<b>Tax Rate</b>", styles["CellBold"]),
                Paragraph("<b>Taxable Amount</b>", styles["CellBold"]),
                Paragraph("<b>CGST Amt.</b>", styles["CellBold"]),
                Paragraph("<b>SGST Amt.</b>", styles["CellBold"]),
                Paragraph("<b>IGST Amt.</b>", styles["CellBold"]),
                Paragraph("<b>Total Tax</b>", styles["CellBold"]),
            ]
        ]
        + tax_summary,
        colWidths=[30 * mm, 35 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm],
    )
    tax_summary_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([tax_summary_table, Spacer(1, 6)])

    rounded_total = quantize_money(invoice.grand_total.quantize(MONEY, rounding=ROUND_HALF_UP))
    totals_table = Table(
        [
            [Paragraph("<b>Sub Total</b>", styles["CellBold"]), Paragraph(format_money(invoice.subtotal), styles["SmallRight"])],
            [Paragraph("<b>CGST</b>", styles["CellBold"]), Paragraph(format_money(invoice.cgst_total), styles["SmallRight"])],
            [Paragraph("<b>SGST</b>", styles["CellBold"]), Paragraph(format_money(invoice.sgst_total), styles["SmallRight"])],
            [Paragraph("<b>IGST</b>", styles["CellBold"]), Paragraph(format_money(invoice.igst_total), styles["SmallRight"])],
            [Paragraph("<b>Discount</b>", styles["CellBold"]), Paragraph(format_money(invoice.discount_total), styles["SmallRight"])],
            [Paragraph("<b>Total</b>", styles["CellBold"]), Paragraph(format_money(invoice.grand_total), styles["SmallRight"])],
            [Paragraph("<b>Total after Round Off</b>", styles["CellBold"]), Paragraph(format_money(rounded_total), styles["SmallRight"])],
        ],
        colWidths=[55 * mm, 35 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BACKGROUND", (0, 5), (-1, 6), colors.HexColor("#f3f4f6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([totals_table, Spacer(1, 8)])

    account_details = _build_account_details(invoice)
    footer_table = Table(
        [
            [
                Paragraph("<b>Account Details</b>", styles["SectionLabel"]),
                Paragraph("<b>Terms &amp; Conditions</b>", styles["SectionLabel"]),
            ],
            [
                Paragraph(_pdf_multiline(account_details), styles["Cell"]),
                Paragraph(
                    "<br/>".join(
                        [
                            "1. E. &amp; O.E.",
                            "2. Goods/services once sold will not be taken back.",
                            "3. Interest @ 18% p.a. may apply on overdue balances.",
                            "4. Subject to local jurisdiction.",
                        ]
                    ),
                    styles["Cell"],
                ),
            ],
            [
                Paragraph("", styles["Cell"]),
                Paragraph("<b>For Authorised Signatory</b><br/><br/>________________________", styles["Cell"]),
            ],
        ],
        colWidths=[95 * mm, 85 * mm],
    )
    footer_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f9fafb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(footer_table)

    document.build(story, canvasmaker=UncompressedCanvas)
    return buffer.getvalue()


def render_invoice_pdf_fallback(invoice: Invoice) -> bytes:
    buffer = io.BytesIO()
    canvas = UncompressedCanvas(buffer, pagesize=A4)
    width, height = A4
    left = 18 * mm
    right = width - 18 * mm
    y = height - 18 * mm

    def clean(value, default: str = "-") -> str:
        if value in ("", None):
            value = default
        return str(value).replace("\r", " ").replace("\n", " ")

    def draw(label: str, value, *, bold: bool = False) -> None:
        nonlocal y
        canvas.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        canvas.drawString(left, y, f"{label}: {clean(value)}"[:115])
        y -= 7 * mm

    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(left, y, "Tax Invoice")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(right, y, "Generated by OMMS")
    y -= 12 * mm

    draw("Invoice No.", invoice.invoice_number, bold=True)
    draw("Invoice Date", invoice.invoice_date.strftime("%d-%m-%Y") if invoice.invoice_date else "-")
    draw("Due Date", invoice.due_date.strftime("%d-%m-%Y") if invoice.due_date else "-")
    draw("Client", invoice.client_legal_name, bold=True)
    draw("Campaign", invoice.campaign.name if invoice.campaign_id else "-")
    y -= 3 * mm

    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(left, y, "Line items")
    y -= 7 * mm
    canvas.setFont("Helvetica", 9)
    for index, line in enumerate(invoice.lines.all().order_by("line_number", "id"), start=1):
        description = clean(line.item_description or line.description)
        amount = format_money(line.line_total)
        canvas.drawString(left, y, f"{index}. {description}"[:90])
        canvas.drawRightString(right, y, amount)
        y -= 6 * mm
        if y < 30 * mm:
            canvas.showPage()
            y = height - 18 * mm
            canvas.setFont("Helvetica", 9)

    y -= 4 * mm
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(left, y, "Total")
    canvas.drawRightString(right, y, format_money(invoice.grand_total))
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _build_service_location(invoice: Invoice) -> str:
    parts = []
    first_line = next(iter(invoice.lines.all().order_by("line_number", "id")), None)
    booking = getattr(first_line, "booking", None)
    media_unit = getattr(booking, "media_unit", None)
    site = getattr(media_unit, "site", None)
    if site:
        location = ", ".join(filter(None, [site.name, site.address, site.city, site.state]))
        parts.append(location)
    elif invoice.campaign:
        parts.append(invoice.campaign.name)
    return "\n".join(filter(None, parts))


def _build_campaign_description(invoice: Invoice) -> str:
    first_line = next(iter(invoice.lines.all().order_by("line_number", "id")), None)
    booking = getattr(first_line, "booking", None)
    media_unit = getattr(booking, "media_unit", None)
    site = getattr(media_unit, "site", None)
    site_label = site.name if site else invoice.campaign.name if invoice.campaign_id else ""
    prefix = "Hoarding Display"
    line_description = (first_line.item_description or first_line.description) if first_line else ""
    if site_label:
        return f"{prefix} - {site_label}"
    return line_description or prefix


def _build_campaign_period(invoice: Invoice) -> str:
    if invoice.campaign and invoice.campaign.start_date and invoice.campaign.end_date:
        return f"{invoice.campaign.start_date:%d-%m-%Y} to {invoice.campaign.end_date:%d-%m-%Y}"
    if invoice.invoice_date and invoice.due_date:
        return f"{invoice.invoice_date:%d-%m-%Y} to {invoice.due_date:%d-%m-%Y}"
    return ""


def _build_qty_size_label(quantity, media_unit) -> str:
    if media_unit and media_unit.width and media_unit.height:
        return f"{quantity} / {media_unit.width}x{media_unit.height}"
    return str(quantity)


def _build_tax_summary_rows(invoice: Invoice) -> list[list[Paragraph]]:
    styles = getSampleStyleSheet()
    cell = ParagraphStyle(name="TaxCell", parent=styles["Normal"], fontSize=8.5, leading=10.5)
    right = ParagraphStyle(name="TaxRight", parent=styles["Normal"], fontSize=8.5, leading=10.5, alignment=TA_RIGHT)

    groups: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "taxable": ZERO,
            "cgst": ZERO,
            "sgst": ZERO,
            "igst": ZERO,
        }
    )
    for line in invoice.lines.all().order_by("line_number", "id"):
        rate_key = format(line.gst_rate, "g")
        groups[rate_key]["taxable"] += quantize_money(line.taxable_value)
        groups[rate_key]["cgst"] += quantize_money(line.cgst_amount)
        groups[rate_key]["sgst"] += quantize_money(line.sgst_amount)
        groups[rate_key]["igst"] += quantize_money(line.igst_amount)

    rows = []
    for rate, values in groups.items():
        total_tax = values["cgst"] + values["sgst"] + values["igst"]
        rows.append(
            [
                Paragraph(f"{rate}%", cell),
                Paragraph(format_money(values["taxable"]), right),
                Paragraph(format_money(values["cgst"]), right),
                Paragraph(format_money(values["sgst"]), right),
                Paragraph(format_money(values["igst"]), right),
                Paragraph(format_money(total_tax), right),
            ]
        )
    if not rows:
        rows.append(
            [
                Paragraph("-", cell),
                Paragraph("0.00", right),
                Paragraph("0.00", right),
                Paragraph("0.00", right),
                Paragraph("0.00", right),
                Paragraph("0.00", right),
            ]
        )
    return rows


def _build_account_details(invoice: Invoice) -> str:
    bank_details = ""
    if invoice.supplier_profile and invoice.supplier_profile.bank_details:
        bank_details = invoice.supplier_profile.bank_details.strip()
    if bank_details:
        return bank_details
    return "A/c Holder: -\nBank Name & Branch: -\nA/c No.: -\nIFSC: -"
