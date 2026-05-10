from __future__ import annotations

import io
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .models import Invoice

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 11 * mm
MARGIN_TOP = 10 * mm
MARGIN_BOTTOM = 10 * mm
TABLE_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)

FOREST = colors.HexColor("#0f513d")
FOREST_DARK = colors.HexColor("#063f2e")
MINT = colors.HexColor("#eef8f3")
MINT_DARK = colors.HexColor("#d8eee5")
GRID = colors.HexColor("#8aa99b")
TEXT = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#52635c")
WHITE = colors.white


def quantize_money(value: Decimal | int | str | None) -> Decimal:
    if value in ("", None):
        value = ZERO
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def format_money(value: Decimal | int | str | None) -> str:
    return f"{quantize_money(value):,.2f}"


def build_safe_invoice_pdf_name(invoice_number: str) -> str:
    safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", invoice_number.strip()).strip("_")
    return f"{safe_number or 'invoice'}.pdf"


def build_invoice_pdf_storage_name(invoice: Invoice) -> str:
    financial_year = invoice.financial_year or "draft"
    filename = build_safe_invoice_pdf_name(invoice.invoice_number or f"invoice_{invoice.pk}")
    return f"invoices/{financial_year}/{filename}"


class UncompressedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("pageCompression", 0)
        super().__init__(*args, **kwargs)


def render_invoice_pdf(invoice: Invoice) -> bytes:
    return _render_standard_invoice(invoice)


def render_invoice_pdf_fallback(invoice: Invoice) -> bytes:
    return _render_standard_invoice(invoice)


def render_invoice_pdf_last_resort(*, invoice_id=None, invoice_number=None) -> bytes:
    buffer = io.BytesIO()
    canvas = UncompressedCanvas(buffer, pagesize=A4)
    _draw_page_chrome(canvas, title="Invoice PDF")
    y = PAGE_HEIGHT - 34 * mm
    _draw_text(canvas, "Invoice PDF", MARGIN_X, y, font="Helvetica-Bold", size=18, color=FOREST_DARK)
    y -= 10 * mm
    _draw_text(canvas, f"Invoice: {_clean(invoice_number or invoice_id)}", MARGIN_X, y, font="Helvetica-Bold", size=10)
    y -= 8 * mm
    _draw_text(
        canvas,
        "A simplified PDF was generated because the invoice details could not be loaded.",
        MARGIN_X,
        y,
        size=9,
    )
    y -= 7 * mm
    _draw_text(canvas, "Please contact the OMMS administrator for the full tax invoice.", MARGIN_X, y, size=9)
    _draw_footer(canvas, 1)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _render_standard_invoice(invoice: Invoice) -> bytes:
    buffer = io.BytesIO()
    canvas = UncompressedCanvas(buffer, pagesize=A4)
    page_number = 1

    _draw_page_chrome(canvas)
    y = PAGE_HEIGHT - MARGIN_TOP
    y = _draw_header(canvas, invoice, y)
    y = _draw_party_blocks(canvas, invoice, y)
    y = _draw_campaign_block(canvas, invoice, y)
    y, page_number = _draw_line_table(canvas, invoice, y, page_number)

    if y < 142 * mm:
        _draw_footer(canvas, page_number)
        canvas.showPage()
        page_number += 1
        _draw_page_chrome(canvas)
        y = PAGE_HEIGHT - 22 * mm

    y = _draw_summary_section(canvas, invoice, y)
    _draw_footer_blocks(canvas, invoice, y)
    _draw_footer(canvas, page_number)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _draw_page_chrome(canvas: Canvas, *, title: str = "Tax Invoice") -> None:
    canvas.setFillColor(FOREST)
    canvas.rect(0, PAGE_HEIGHT - 8 * mm, PAGE_WIDTH, 8 * mm, stroke=0, fill=1)
    canvas.setStrokeColor(MINT_DARK)
    canvas.setLineWidth(0.8)
    canvas.rect(MARGIN_X - 3 * mm, MARGIN_BOTTOM - 3 * mm, TABLE_WIDTH + 6 * mm, PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM, stroke=1, fill=0)
    canvas.setFillColor(FOREST_DARK)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT - 15 * mm, title)


def _draw_header(canvas: Canvas, invoice: Invoice, y: float) -> float:
    y -= 22 * mm
    _draw_text(canvas, "Outdoor Media Operations & Execution Management System", MARGIN_X, y, size=7.5, color=MUTED)
    _draw_text(canvas, "Original for Recipient", PAGE_WIDTH - MARGIN_X - 83, y, size=7.5, color=MUTED)
    y -= 5 * mm
    canvas.setStrokeColor(FOREST)
    canvas.setLineWidth(1)
    canvas.line(MARGIN_X, y, PAGE_WIDTH - MARGIN_X, y)
    return y - 4 * mm


def _draw_party_blocks(canvas: Canvas, invoice: Invoice, y: float) -> float:
    box_gap = 4 * mm
    box_width = (TABLE_WIDTH - box_gap) / 2
    top = y
    supplier_height = 36 * mm
    bill_height = 34 * mm

    supplier_lines = _supplier_lines(invoice)
    invoice_lines = [
        ("Invoice No.", invoice.invoice_number or f"Draft #{invoice.pk}"),
        ("Invoice Date", _date(invoice.invoice_date)),
        ("Due Date", _date(invoice.due_date)),
        ("Financial Year", invoice.financial_year or "-"),
        ("Reverse Charge", "Yes" if invoice.reverse_charge else "No"),
        ("Place of Supply", _join_state(invoice.place_of_supply_state, invoice.place_of_supply_state_code)),
    ]
    _draw_info_box(canvas, MARGIN_X, top, box_width, supplier_height, "Supplier Details", supplier_lines)
    _draw_key_value_box(canvas, MARGIN_X + box_width + box_gap, top, box_width, supplier_height, "Invoice Details", invoice_lines)

    top -= supplier_height + box_gap
    bill_to_lines = _bill_to_lines(invoice)
    service_lines = [
        ("Service Location", _build_service_location(invoice) or "-"),
        ("Campaign", _campaign_label(invoice)),
        ("Campaign Period", _build_campaign_period(invoice) or "-"),
    ]
    _draw_info_box(canvas, MARGIN_X, top, box_width, bill_height, "Bill To", bill_to_lines)
    _draw_key_value_box(canvas, MARGIN_X + box_width + box_gap, top, box_width, bill_height, "Service / Shipping Details", service_lines)
    return top - bill_height - 4 * mm


def _draw_campaign_block(canvas: Canvas, invoice: Invoice, y: float) -> float:
    height = 17 * mm
    _draw_box(canvas, MARGIN_X, y, TABLE_WIDTH, height, fill=MINT)
    _draw_text(canvas, "Campaign / Booking Summary", MARGIN_X + 3 * mm, y - 5 * mm, font="Helvetica-Bold", size=8, color=FOREST_DARK)
    details = [
        f"Campaign: {_campaign_label(invoice)}",
        f"Service: {_build_campaign_description(invoice)}",
        f"Payment Terms: {invoice.payment_terms or '-'}",
    ]
    _draw_wrapped_text(canvas, " | ".join(details), MARGIN_X + 3 * mm, y - 10 * mm, TABLE_WIDTH - 6 * mm, size=7.3, leading=8)
    return y - height - 4 * mm


def _draw_line_table(canvas: Canvas, invoice: Invoice, y: float, page_number: int) -> tuple[float, int]:
    columns = [
        ("#", 18),
        ("Description", 111),
        ("Period", 45),
        ("HSN/SAC", 33),
        ("Qty", 29),
        ("Rate", 42),
        ("Taxable", 47),
        ("GST%", 29),
        ("CGST", 38),
        ("SGST", 38),
        ("IGST", 38),
        ("Total", 44),
    ]
    rows = list(invoice.lines.all().order_by("line_number", "id"))
    if not rows:
        rows = [None]

    y = _draw_table_header(canvas, y, columns)
    for index, line in enumerate(rows, start=1):
        description = "No line items available."
        values = ["", "", "", "", "", "", "", "", "", "", ""]
        if line is not None:
            description = _line_description(line)
            values = [
                _line_period(line, invoice),
                line.hsn_code or line.sac_code or "-",
                _decimal_label(line.quantity),
                format_money(line.unit_price),
                format_money(line.taxable_value),
                _percent(line.gst_rate),
                format_money(line.cgst_amount),
                format_money(line.sgst_amount),
                format_money(line.igst_amount),
                format_money(line.line_total),
            ]
        row_values = [str(index), description, *values]
        row_height = _calculate_row_height(canvas, row_values, columns, size=6.5, leading=7.2)
        if y - row_height < 28 * mm:
            _draw_footer(canvas, page_number)
            canvas.showPage()
            page_number += 1
            _draw_page_chrome(canvas)
            y = PAGE_HEIGHT - 24 * mm
            _draw_text(canvas, f"Invoice No.: {invoice.invoice_number or f'Draft #{invoice.pk}'}", MARGIN_X, y, font="Helvetica-Bold", size=8)
            y -= 7 * mm
            y = _draw_table_header(canvas, y, columns)
        _draw_table_row(canvas, y, columns, row_values, row_height)
        y -= row_height
    return y - 4 * mm, page_number


def _draw_summary_section(canvas: Canvas, invoice: Invoice, y: float) -> float:
    tax_rows = _build_tax_summary(invoice)
    tax_width = 285
    totals_width = TABLE_WIDTH - tax_width - 8 * mm
    tax_x = MARGIN_X
    totals_x = MARGIN_X + tax_width + 8 * mm
    top = y

    _draw_box(canvas, tax_x, top, tax_width, 37 * mm, fill=WHITE)
    _draw_text(canvas, "Tax Summary", tax_x + 3 * mm, top - 5 * mm, font="Helvetica-Bold", size=8, color=FOREST_DARK)
    summary_columns = [("Rate", 40), ("Taxable", 58), ("CGST", 48), ("SGST", 48), ("IGST", 48), ("Tax", 43)]
    row_y = top - 9 * mm
    row_y = _draw_table_header(canvas, row_y, summary_columns, height=6 * mm, size=6.4)
    for tax_row in tax_rows[:3]:
        row_values = [
            f"{tax_row['rate']}%",
            format_money(tax_row["taxable"]),
            format_money(tax_row["cgst"]),
            format_money(tax_row["sgst"]),
            format_money(tax_row["igst"]),
            format_money(tax_row["total_tax"]),
        ]
        _draw_table_row(canvas, row_y, summary_columns, row_values, 6 * mm, size=6.4)
        row_y -= 6 * mm

    _draw_box(canvas, totals_x, top, totals_width, 37 * mm, fill=MINT)
    totals = [
        ("Subtotal", invoice.subtotal),
        ("Discount", invoice.discount_total),
        ("CGST", invoice.cgst_total),
        ("SGST", invoice.sgst_total),
        ("IGST", invoice.igst_total),
        ("Grand Total", invoice.grand_total),
    ]
    row_y = top - 5 * mm
    for label, value in totals:
        font = "Helvetica-Bold" if label == "Grand Total" else "Helvetica"
        size = 8.5 if label == "Grand Total" else 7.4
        _draw_text(canvas, label, totals_x + 4 * mm, row_y, font=font, size=size, color=FOREST_DARK if label == "Grand Total" else TEXT)
        _draw_text(canvas, format_money(value), totals_x + totals_width - 4 * mm, row_y, font=font, size=size, align="right")
        row_y -= 5 * mm

    y = top - 42 * mm
    amount_words = amount_to_words(invoice.grand_total)
    _draw_box(canvas, MARGIN_X, y, TABLE_WIDTH, 11 * mm, fill=MINT)
    _draw_text(canvas, "Amount in Words", MARGIN_X + 3 * mm, y - 4 * mm, font="Helvetica-Bold", size=7, color=FOREST_DARK)
    _draw_wrapped_text(canvas, amount_words, MARGIN_X + 35 * mm, y - 4 * mm, TABLE_WIDTH - 38 * mm, font="Helvetica-Bold", size=7.4, leading=8)
    return y - 15 * mm


def _draw_footer_blocks(canvas: Canvas, invoice: Invoice, y: float) -> None:
    box_gap = 4 * mm
    box_width = (TABLE_WIDTH - box_gap) / 2
    height = 34 * mm
    terms = [
        "1. E. & O.E.",
        "2. Subject to local jurisdiction.",
        "3. Interest may apply on overdue balances.",
        "4. This invoice is generated from confirmed OMMS bookings.",
    ]
    _draw_info_box(canvas, MARGIN_X, y, box_width, height, "Bank / Payment Details", _split_lines(_build_account_details(invoice)))
    _draw_info_box(canvas, MARGIN_X + box_width + box_gap, y, box_width, height, "Terms & Conditions", terms)

    sign_y = y - height - 6 * mm
    _draw_text(canvas, "For Authorised Signatory", PAGE_WIDTH - MARGIN_X - 3 * mm, sign_y, font="Helvetica-Bold", size=8, align="right")
    canvas.setStrokeColor(GRID)
    canvas.line(PAGE_WIDTH - MARGIN_X - 52 * mm, sign_y - 12 * mm, PAGE_WIDTH - MARGIN_X - 3 * mm, sign_y - 12 * mm)


def _draw_info_box(canvas: Canvas, x: float, top: float, width: float, height: float, title: str, lines: list[str]) -> None:
    _draw_box(canvas, x, top, width, height, fill=WHITE)
    _draw_section_title(canvas, x, top, width, title)
    y = top - 9 * mm
    first = True
    for line in [line for line in lines if _clean(line, default="")]:
        font = "Helvetica-Bold" if first else "Helvetica"
        size = 7.6 if first else 7.1
        used_lines = _draw_wrapped_text(canvas, line, x + 3 * mm, y, width - 6 * mm, font=font, size=size, leading=7.8, max_lines=2)
        y -= max(used_lines, 1) * 4 * mm
        first = False
        if y < top - height + 5 * mm:
            break


def _draw_key_value_box(canvas: Canvas, x: float, top: float, width: float, height: float, title: str, rows: list[tuple[str, str]]) -> None:
    _draw_box(canvas, x, top, width, height, fill=WHITE)
    _draw_section_title(canvas, x, top, width, title)
    y = top - 9 * mm
    for label, value in rows:
        _draw_text(canvas, label, x + 3 * mm, y, font="Helvetica-Bold", size=7.1, color=MUTED)
        used_lines = _draw_wrapped_text(canvas, _clean(value), x + 29 * mm, y, width - 32 * mm, size=7.1, leading=7.6, max_lines=2)
        y -= max(used_lines, 1) * 4 * mm
        if y < top - height + 5 * mm:
            break


def _draw_section_title(canvas: Canvas, x: float, top: float, width: float, title: str) -> None:
    canvas.setFillColor(MINT_DARK)
    canvas.rect(x, top - 7 * mm, width, 7 * mm, stroke=0, fill=1)
    _draw_text(canvas, title, x + 3 * mm, top - 4.8 * mm, font="Helvetica-Bold", size=7.5, color=FOREST_DARK)


def _draw_box(canvas: Canvas, x: float, top: float, width: float, height: float, *, fill=WHITE) -> None:
    canvas.setFillColor(fill)
    canvas.setStrokeColor(GRID)
    canvas.setLineWidth(0.55)
    canvas.rect(x, top - height, width, height, stroke=1, fill=1)


def _draw_table_header(canvas: Canvas, y: float, columns: list[tuple[str, float]], *, height: float = 7 * mm, size: float = 6.2) -> float:
    x = MARGIN_X
    for label, width in columns:
        _draw_cell(canvas, x, y, width, height, label, font="Helvetica-Bold", size=size, fill=FOREST, color=WHITE, align="center")
        x += width
    return y - height


def _draw_table_row(canvas: Canvas, y: float, columns: list[tuple[str, float]], values: list[str], height: float, *, size: float = 6.5) -> None:
    x = MARGIN_X
    for index, ((_, width), value) in enumerate(zip(columns, values)):
        align = "right" if index >= 5 else "left"
        if index in {0, 3, 4, 7}:
            align = "center"
        _draw_cell(canvas, x, y, width, height, value, size=size, align=align)
        x += width


def _draw_cell(
    canvas: Canvas,
    x: float,
    top: float,
    width: float,
    height: float,
    text: str,
    *,
    font: str = "Helvetica",
    size: float = 6.5,
    fill=WHITE,
    color=TEXT,
    align: str = "left",
) -> None:
    canvas.setFillColor(fill)
    canvas.setStrokeColor(GRID)
    canvas.setLineWidth(0.4)
    canvas.rect(x, top - height, width, height, stroke=1, fill=1)
    _draw_wrapped_text(canvas, text, x + 2, top - 4, max(width - 4, 4), font=font, size=size, leading=size + 1.1, color=color, align=align)


def _calculate_row_height(canvas: Canvas, values: list[str], columns: list[tuple[str, float]], *, size: float, leading: float) -> float:
    line_counts = [
        len(_wrap_text(_clean(value), max(width - 4, 4), font="Helvetica", size=size))
        for value, (_, width) in zip(values, columns)
    ]
    return max(9 * mm, (max(line_counts or [1]) * leading) + 6)


def _draw_text(
    canvas: Canvas,
    text: str,
    x: float,
    y: float,
    *,
    font: str = "Helvetica",
    size: float = 8,
    color=TEXT,
    align: str = "left",
) -> None:
    value = _clean(text)
    canvas.setFont(font, size)
    canvas.setFillColor(color)
    if align == "right":
        canvas.drawRightString(x, y, value)
    elif align == "center":
        canvas.drawCentredString(x, y, value)
    else:
        canvas.drawString(x, y, value)


def _draw_wrapped_text(
    canvas: Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font: str = "Helvetica",
    size: float = 8,
    leading: float = 9,
    color=TEXT,
    max_lines: int | None = None,
    align: str = "left",
) -> int:
    lines = _wrap_text(_clean(text), width, font=font, size=size)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _truncate_to_width(lines[-1] + "...", width, font, size)
    for offset, line in enumerate(lines):
        _draw_text(canvas, line, x if align != "right" else x + width, y - (offset * leading), font=font, size=size, color=color, align=align)
    return len(lines)


def _wrap_text(text: str, width: float, *, font: str, size: float) -> list[str]:
    if not text:
        return ["-"]
    result: list[str] = []
    for paragraph in str(text).splitlines() or [str(text)]:
        words = paragraph.split()
        if not words:
            result.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if stringWidth(candidate, font, size) <= width:
                line = candidate
                continue
            result.extend(_break_long_word(line, width, font, size))
            line = word
        result.extend(_break_long_word(line, width, font, size))
    return result or ["-"]


def _break_long_word(word: str, width: float, font: str, size: float) -> list[str]:
    if stringWidth(word, font, size) <= width:
        return [word]
    pieces: list[str] = []
    current = ""
    for char in word:
        candidate = current + char
        if current and stringWidth(candidate, font, size) > width:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces or [word]


def _truncate_to_width(text: str, width: float, font: str, size: float) -> str:
    value = text
    while value and stringWidth(value, font, size) > width:
        value = value[:-1]
    return value


def _draw_footer(canvas: Canvas, page_number: int) -> None:
    y = 7 * mm
    canvas.setStrokeColor(MINT_DARK)
    canvas.line(MARGIN_X, y + 4 * mm, PAGE_WIDTH - MARGIN_X, y + 4 * mm)
    _draw_text(canvas, "Generated by OMMS", MARGIN_X, y, size=6.8, color=MUTED)
    _draw_text(canvas, f"Page {page_number}", PAGE_WIDTH - MARGIN_X, y, size=6.8, color=MUTED, align="right")


def _supplier_lines(invoice: Invoice) -> list[str]:
    name = invoice.supplier_trade_name or invoice.supplier_legal_name or "Supplier"
    legal_name = invoice.supplier_legal_name if invoice.supplier_trade_name and invoice.supplier_legal_name != invoice.supplier_trade_name else ""
    address = _join(
        invoice.supplier_address_line_1,
        invoice.supplier_address_line_2,
        invoice.supplier_city,
        invoice.supplier_state,
        invoice.supplier_postal_code,
        invoice.supplier_country,
    )
    return [
        name,
        legal_name,
        address,
        f"GSTIN: {invoice.supplier_gstin or '-'} | State Code: {invoice.supplier_state_code or '-'}",
        _join(f"Email: {invoice.supplier_contact_email}" if invoice.supplier_contact_email else "", f"Phone: {invoice.supplier_contact_phone}" if invoice.supplier_contact_phone else "", sep=" | "),
    ]


def _bill_to_lines(invoice: Invoice) -> list[str]:
    address = _join(
        invoice.client_billing_address_line_1,
        invoice.client_billing_address_line_2,
        invoice.client_billing_city,
        invoice.client_billing_state,
        invoice.client_billing_postal_code,
        invoice.client_billing_country,
    )
    return [
        invoice.client_legal_name or "Client",
        address or "-",
        f"GSTIN: {invoice.client_gstin or '-'} | State Code: {invoice.client_billing_state_code or '-'}",
    ]


def _line_description(line) -> str:
    parts = [
        line.item_description or line.description or "Outdoor media display",
        f"Site: {line.site_name}" if line.site_name else "",
        f"Media Unit: {line.media_unit_label}" if line.media_unit_label else "",
    ]
    return _join(*parts, sep=" | ")


def _line_period(line, invoice: Invoice) -> str:
    start = line.booking_start_date or getattr(invoice.campaign, "start_date", None)
    end = line.booking_end_date or getattr(invoice.campaign, "end_date", None)
    if start and end:
        return f"{_date(start)} to {_date(end)}"
    return "-"


def _build_tax_summary(invoice: Invoice) -> list[dict[str, Decimal | str]]:
    groups: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO}
    )
    for line in invoice.lines.all().order_by("line_number", "id"):
        rate_key = format(quantize_money(line.gst_rate or ZERO), "g")
        groups[rate_key]["taxable"] += quantize_money(line.taxable_value)
        groups[rate_key]["cgst"] += quantize_money(line.cgst_amount)
        groups[rate_key]["sgst"] += quantize_money(line.sgst_amount)
        groups[rate_key]["igst"] += quantize_money(line.igst_amount)

    rows = []
    for rate, values in sorted(groups.items(), key=lambda item: Decimal(item[0])):
        total_tax = values["cgst"] + values["sgst"] + values["igst"]
        rows.append({"rate": rate, **values, "total_tax": total_tax})
    return rows or [{"rate": "-", "taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO, "total_tax": ZERO}]


def _build_service_location(invoice: Invoice) -> str:
    first_line = next(iter(invoice.lines.all().order_by("line_number", "id")), None)
    booking = getattr(first_line, "booking", None)
    media_unit = getattr(booking, "media_unit", None)
    site = getattr(media_unit, "site", None)
    if site:
        return _join(site.name, site.address, site.city, site.state)
    return _campaign_label(invoice)


def _build_campaign_description(invoice: Invoice) -> str:
    first_line = next(iter(invoice.lines.all().order_by("line_number", "id")), None)
    if first_line and (first_line.item_description or first_line.description):
        return first_line.item_description or first_line.description
    return "Outdoor media display services"


def _build_campaign_period(invoice: Invoice) -> str:
    if invoice.campaign and invoice.campaign.start_date and invoice.campaign.end_date:
        return f"{_date(invoice.campaign.start_date)} to {_date(invoice.campaign.end_date)}"
    if invoice.invoice_date and invoice.due_date:
        return f"{_date(invoice.invoice_date)} to {_date(invoice.due_date)}"
    return ""


def _build_account_details(invoice: Invoice) -> str:
    if invoice.supplier_profile and invoice.supplier_profile.bank_details:
        return invoice.supplier_profile.bank_details.strip()
    return "A/c Holder: -\nBank Name & Branch: -\nA/c No.: -\nIFSC: -"


def amount_to_words(value: Decimal | int | str | None) -> str:
    amount = quantize_money(value)
    rupees = int(amount)
    paise = int((amount - Decimal(rupees)) * 100)
    if rupees == 0:
        words = "Zero"
    else:
        words = _number_to_words_indian(rupees)
    if paise:
        return f"INR {words} and Paise {_number_to_words_indian(paise)} Only"
    return f"INR {words} Only"


def _number_to_words_indian(number: int) -> str:
    ones = [
        "",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def below_thousand(value: int) -> str:
        parts = []
        if value >= 100:
            parts.append(f"{ones[value // 100]} Hundred")
            value %= 100
        if value >= 20:
            parts.append(tens[value // 10])
            value %= 10
        if value:
            parts.append(ones[value])
        return " ".join(parts)

    parts = []
    for divisor, label in [(10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")]:
        if number >= divisor:
            count, number = divmod(number, divisor)
            parts.append(f"{below_thousand(count)} {label}")
    if number:
        parts.append(below_thousand(number))
    return " ".join(part for part in parts if part).strip()


def _campaign_label(invoice: Invoice) -> str:
    if invoice.campaign_id:
        code = getattr(invoice.campaign, "code", "")
        name = getattr(invoice.campaign, "name", "")
        return _join(name, code, sep=" / ")
    return "-"


def _join(*parts, sep: str = ", ") -> str:
    return sep.join(_clean(part, default="") for part in parts if _clean(part, default=""))


def _join_state(state, code) -> str:
    if state and code:
        return f"{state} ({code})"
    return state or code or "-"


def _split_lines(value: str) -> list[str]:
    return [_clean(line, default="") for line in str(value or "").splitlines() if _clean(line, default="")]


def _date(value) -> str:
    if not value:
        return "-"
    return value.strftime("%d-%m-%Y")


def _percent(value) -> str:
    return f"{format(quantize_money(value), 'g')}%"


def _decimal_label(value) -> str:
    return format(quantize_money(value), "g")


def _clean(value, default: str = "-") -> str:
    if value in ("", None):
        value = default
    return re.sub(r"\s+", " ", str(value)).strip()
