from __future__ import annotations

import io
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from .models import Invoice

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 13 * mm
MARGIN_TOP = 9 * mm
MARGIN_BOTTOM = 15 * mm
TABLE_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)
CONTENT_BOTTOM = MARGIN_BOTTOM + 8 * mm

FOREST = colors.HexColor("#0f513d")
FOREST_DARK = colors.HexColor("#073b2c")
FOREST_SOFT = colors.HexColor("#eaf6ef")
MINT = colors.HexColor("#f3faf6")
MINT_DARK = colors.HexColor("#d8eee5")
TEXT = colors.HexColor("#17211d")
MUTED = colors.HexColor("#62736c")
BORDER = colors.HexColor("#dbe7e1")
BORDER_DARK = colors.HexColor("#9fb8ad")
TABLE_HEADER = colors.HexColor("#0b4a37")
TABLE_ALT = colors.HexColor("#fbfdfc")
WHITE = colors.white

CELL_PAD_X = 4
CELL_PAD_Y = 4


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


class InvoiceCanvas(UncompressedCanvas):
    """Stores pages so the footer can render Page X of Y without a second PDF pass."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        state = dict(self.__dict__)
        state["_saved_page_states"] = []
        self._saved_page_states.append(state)
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            _draw_footer(self, self._pageNumber, page_count)
            Canvas.showPage(self)
        Canvas.save(self)


def render_invoice_pdf(invoice: Invoice) -> bytes:
    return _render_standard_invoice(invoice)


def render_invoice_pdf_fallback(invoice: Invoice) -> bytes:
    return _render_standard_invoice(invoice)


def render_invoice_pdf_last_resort(*, invoice_id=None, invoice_number=None) -> bytes:
    buffer = io.BytesIO()
    canvas = UncompressedCanvas(buffer, pagesize=A4)
    _draw_page_top_accent(canvas)
    _draw_text(canvas, "Invoice PDF", MARGIN_X, PAGE_HEIGHT - 34 * mm, font="Helvetica-Bold", size=20, color=FOREST_DARK)
    _draw_text(canvas, f"Invoice: {_clean(invoice_number or invoice_id)}", MARGIN_X, PAGE_HEIGHT - 46 * mm, font="Helvetica-Bold", size=10)
    _draw_text(
        canvas,
        "A simplified PDF was generated because the invoice details could not be loaded.",
        MARGIN_X,
        PAGE_HEIGHT - 58 * mm,
        size=9,
    )
    _draw_text(canvas, "Please contact the OMMS administrator for the full tax invoice.", MARGIN_X, PAGE_HEIGHT - 66 * mm, size=9)
    _draw_footer(canvas, 1)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _render_standard_invoice(invoice: Invoice) -> bytes:
    buffer = io.BytesIO()
    canvas = InvoiceCanvas(buffer, pagesize=A4)
    page_number = 1

    y = _draw_page_header(canvas, invoice, page_number)
    y = _draw_invoice_meta(canvas, invoice, y)
    y = _draw_party_cards(canvas, invoice, y)
    y = _draw_service_summary(canvas, invoice, y)
    y, page_number = _draw_line_items_table(canvas, invoice, y, page_number)

    summary_space = _summary_section_height(invoice)
    if y < CONTENT_BOTTOM + summary_space:
        y, page_number = _new_page(canvas, invoice, page_number)

    y = _draw_financial_summary(canvas, invoice, y)

    if y < CONTENT_BOTTOM + 43 * mm:
        y, page_number = _new_page(canvas, invoice, page_number)

    _draw_payment_terms_and_signature(canvas, invoice, y)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _new_page(canvas: Canvas, invoice: Invoice, page_number: int, *, continued: bool = False) -> tuple[float, int]:
    canvas.showPage()
    page_number += 1
    return _draw_page_header(canvas, invoice, page_number, continued=continued), page_number


def _draw_page_top_accent(canvas: Canvas) -> None:
    canvas.setFillColor(FOREST)
    canvas.rect(0, PAGE_HEIGHT - 3.2 * mm, PAGE_WIDTH, 3.2 * mm, stroke=0, fill=1)


def _draw_page_header(canvas: Canvas, invoice: Invoice, page_number: int, *, continued: bool = False) -> float:
    _draw_page_top_accent(canvas)
    profile = _get_company_profile()
    top = PAGE_HEIGHT - MARGIN_TOP

    _draw_company_identity(canvas, invoice, profile, MARGIN_X, top, TABLE_WIDTH * 0.62)

    right_x = PAGE_WIDTH - MARGIN_X
    _draw_text(canvas, "Tax Invoice", right_x, top - 1 * mm, font="Helvetica-Bold", size=21, color=FOREST_DARK, align="right")
    _draw_text(canvas, "Original for Recipient", right_x, top - 8.5 * mm, size=7.3, color=MUTED, align="right")
    if continued:
        _draw_text(canvas, "Invoice items continued", right_x, top - 15 * mm, size=7.3, color=MUTED, align="right")

    y = top - 19 * mm
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.8)
    canvas.line(MARGIN_X, y, PAGE_WIDTH - MARGIN_X, y)
    return y - 3.5 * mm


def _draw_company_identity(canvas: Canvas, invoice: Invoice, profile, x: float, top: float, width: float) -> None:
    company_name = _company_display_name(invoice, profile)
    logo_drawn = _draw_company_logo(canvas, profile, x, top, 20 * mm, 15 * mm)
    text_x = x + (24 * mm if logo_drawn else 0)
    text_width = width - (24 * mm if logo_drawn else 0)

    _draw_wrapped_text(canvas, company_name, text_x, top - 0.5 * mm, text_width, font="Helvetica-Bold", size=12.4, leading=13.2, color=FOREST_DARK, max_lines=2)

    y = top - 11.5 * mm
    legal_name = invoice.supplier_legal_name if invoice.supplier_trade_name and invoice.supplier_legal_name != invoice.supplier_trade_name else ""
    if legal_name:
        used = _draw_wrapped_text(canvas, legal_name, text_x, y, text_width, size=7.3, leading=7.8, color=MUTED, max_lines=1)
        y -= max(used, 1) * 3.5 * mm

    contact = _join(
        f"Email: {invoice.supplier_contact_email}" if invoice.supplier_contact_email else "",
        f"Phone: {invoice.supplier_contact_phone}" if invoice.supplier_contact_phone else "",
        sep="  |  ",
    )
    if contact:
        _draw_wrapped_text(canvas, contact, text_x, y, text_width, size=6.9, leading=7.5, color=MUTED, max_lines=2)


def _draw_company_logo(canvas: Canvas, profile, x: float, top: float, max_width: float, max_height: float) -> bool:
    logo = getattr(profile, "logo", None)
    if not logo:
        return False

    try:
        logo.open("rb")
        try:
            image = ImageReader(io.BytesIO(logo.read()))
        finally:
            logo.close()
        image_width, image_height = image.getSize()
        if not image_width or not image_height:
            return False
        scale = min(max_width / image_width, max_height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        canvas.drawImage(image, x, top - draw_height, width=draw_width, height=draw_height, mask="auto")
        return True
    except Exception:
        return False


def _draw_invoice_meta(canvas: Canvas, invoice: Invoice, y: float) -> float:
    rows = _invoice_meta_rows(invoice)
    columns = 4 if len(rows) >= 4 else max(len(rows), 1)
    row_count = ((len(rows) - 1) // columns) + 1
    height = 8 * mm + (row_count * 8 * mm)
    _draw_card(canvas, MARGIN_X, y, TABLE_WIDTH, height, "Invoice Details")

    grid_top = y - 8 * mm
    cell_width = TABLE_WIDTH / columns
    cell_height = 8 * mm
    for index, (label, value) in enumerate(rows):
        col = index % columns
        row = index // columns
        x = MARGIN_X + (col * cell_width)
        cell_top = grid_top - (row * cell_height)
        if col:
            canvas.setStrokeColor(BORDER)
            canvas.setLineWidth(0.4)
            canvas.line(x, cell_top + 2 * mm, x, cell_top - cell_height + 1 * mm)
        _draw_text(canvas, label, x + 3 * mm, cell_top - 1 * mm, font="Helvetica-Bold", size=6.3, color=MUTED)
        _draw_wrapped_text(canvas, value, x + 3 * mm, cell_top - 4 * mm, cell_width - 6 * mm, font="Helvetica-Bold", size=7.3, leading=7.8, color=TEXT, max_lines=1)

    return y - height - 3 * mm


def _invoice_meta_rows(invoice: Invoice) -> list[tuple[str, str]]:
    rows = [
        ("Invoice Number", _clean(invoice.invoice_number or f"Draft #{invoice.pk}")),
        ("Invoice Date", _date(invoice.invoice_date)),
        ("Due Date", _date(invoice.due_date)),
        ("Reverse Charge", "Yes" if invoice.reverse_charge else "No"),
    ]
    if _clean(invoice.financial_year):
        rows.append(("Financial Year", _clean(invoice.financial_year)))
    place_of_supply = _join_state(invoice.place_of_supply_state, invoice.place_of_supply_state_code)
    if place_of_supply:
        rows.append(("Place of Supply", place_of_supply))
    return [(label, value) for label, value in rows if value]


def _draw_party_cards(canvas: Canvas, invoice: Invoice, y: float) -> float:
    gap = 5 * mm
    width = (TABLE_WIDTH - gap) / 2
    height = 35 * mm

    _draw_party_card(canvas, MARGIN_X, y, width, height, "Supplier Details", _supplier_card(invoice))
    _draw_party_card(canvas, MARGIN_X + width + gap, y, width, height, "Bill To", _client_card(invoice))
    return y - height - 4 * mm


def _draw_party_card(canvas: Canvas, x: float, y: float, width: float, height: float, title: str, card: dict[str, list[str] | str]) -> None:
    _draw_card(canvas, x, y, width, height, title)
    content_y = y - 11 * mm
    name_lines = _draw_wrapped_text(canvas, str(card["name"]), x + 4 * mm, content_y, width - 8 * mm, font="Helvetica-Bold", size=8.4, leading=8.8, color=TEXT, max_lines=1)
    content_y -= (max(name_lines, 1) * 3.8 * mm) + 1 * mm
    for line in card["lines"]:
        used = _draw_wrapped_text(canvas, line, x + 4 * mm, content_y, width - 8 * mm, size=6.7, leading=7.2, color=MUTED, max_lines=2)
        content_y -= max(used, 1) * 3.25 * mm
        if content_y < y - height + 5 * mm:
            break


def _draw_service_summary(canvas: Canvas, invoice: Invoice, y: float) -> float:
    items = _service_summary_items(invoice)
    height = _service_summary_height(items)
    _draw_card(canvas, MARGIN_X, y, TABLE_WIDTH, height, "Service / Campaign Summary", fill=MINT)

    x = MARGIN_X + 4 * mm
    content_y = y - 10 * mm
    available = TABLE_WIDTH - 8 * mm
    col_width = available / 2
    row_heights = _service_summary_row_heights(items, col_width)
    row_offsets = []
    offset = 0
    for row_height in row_heights:
        row_offsets.append(offset)
        offset += row_height

    for index, (label, value) in enumerate(items):
        col = index % 2
        row = index // 2
        item_x = x + (col * col_width)
        item_y = content_y - row_offsets[row]
        _draw_text(canvas, label.upper(), item_x, item_y, font="Helvetica-Bold", size=5.8, color=MUTED)
        _draw_wrapped_text(canvas, value, item_x, item_y - 3.2 * mm, col_width - 5 * mm, font="Helvetica-Bold", size=7.2, leading=7.6, color=TEXT)

    return y - height - 4 * mm


def _service_summary_items(invoice: Invoice) -> list[tuple[str, str]]:
    items = [
        ("Campaign", _campaign_label(invoice)),
        ("Duration", _build_campaign_period(invoice)),
        ("Service Location", _build_service_location(invoice)),
        ("Service", _build_campaign_description(invoice)),
        ("Payment Terms", invoice.payment_terms or ""),
    ]
    return [(label, _clean(value)) for label, value in items if _clean(value)]


def _service_summary_row_heights(items: list[tuple[str, str]], col_width: float) -> list[float]:
    row_heights = []
    for row_index in range((len(items) + 1) // 2):
        row_items = items[row_index * 2 : (row_index * 2) + 2]
        max_lines = max(
            len(_wrap_text(value, col_width - 5 * mm, font="Helvetica-Bold", size=7.2))
            for _, value in row_items
        )
        row_heights.append(max(8 * mm, 4.5 * mm + (max_lines * 7.6)))
    return row_heights


def _service_summary_height(items: list[tuple[str, str]]) -> float:
    if not items:
        return 14 * mm
    col_width = (TABLE_WIDTH - 8 * mm) / 2
    return 11 * mm + sum(_service_summary_row_heights(items, col_width)) + 2 * mm


def _draw_line_items_table(canvas: Canvas, invoice: Invoice, y: float, page_number: int) -> tuple[float, int]:
    include_gst = _invoice_has_gst(invoice)
    columns = _line_table_columns(include_gst=include_gst)
    rows = list(invoice.lines.all().order_by("line_number", "id")) or [None]

    _draw_text(canvas, "Invoice Items", MARGIN_X, y, font="Helvetica-Bold", size=11, color=FOREST_DARK)
    _draw_text(canvas, "Amounts in INR", PAGE_WIDTH - MARGIN_X, y, size=7, color=MUTED, align="right")
    y -= 6 * mm
    y = _draw_line_table_header(canvas, y, columns)

    for index, line in enumerate(rows, start=1):
        row = _line_row(line, invoice, index, include_gst=include_gst)
        row_height = _line_row_height(row, columns)
        if y - row_height < CONTENT_BOTTOM + 8 * mm:
            y, page_number = _new_page(canvas, invoice, page_number, continued=True)
            _draw_text(canvas, "Invoice Items (continued)", MARGIN_X, y, font="Helvetica-Bold", size=10, color=FOREST_DARK)
            _draw_text(canvas, "Amounts in INR", PAGE_WIDTH - MARGIN_X, y, size=7, color=MUTED, align="right")
            y -= 6 * mm
            y = _draw_line_table_header(canvas, y, columns)
        _draw_line_table_row(canvas, y, columns, row, row_height, shaded=index % 2 == 0)
        y -= row_height

    return y - 5 * mm, page_number


def _line_table_columns(*, include_gst: bool) -> list[tuple[str, float]]:
    fixed = [
        ("#", 16),
        ("Description", 190 if include_gst else 216),
        ("Period", 54),
        ("HSN/SAC", 42),
        ("Qty", 25),
        ("Rate", 48),
        ("Taxable", 52),
    ]
    if include_gst:
        fixed.append(("GST %", 33))
    fixed_width = sum(width for _, width in fixed)
    return [*fixed, ("Total", TABLE_WIDTH - fixed_width)]


def _draw_line_table_header(canvas: Canvas, y: float, columns: list[tuple[str, float]]) -> float:
    x = MARGIN_X
    height = 7 * mm
    for label, width in columns:
        _draw_cell_box(canvas, x, y, width, height, fill=TABLE_HEADER, stroke=TABLE_HEADER)
        _draw_cell_text(canvas, x, y, width, height, label, font="Helvetica-Bold", size=6.5, color=WHITE, align="center")
        x += width
    return y - height


def _draw_line_table_row(canvas: Canvas, y: float, columns: list[tuple[str, float]], row: dict, height: float, *, shaded: bool) -> None:
    x = MARGIN_X
    fill = TABLE_ALT if shaded else WHITE
    for index, (label, width) in enumerate(columns):
        _draw_cell_box(canvas, x, y, width, height, fill=fill, stroke=BORDER)
        if label == "Description":
            _draw_description_cell(canvas, x, y, width, height, row["description"])
        else:
            value = row["values"].get(label, "")
            align = "right" if label in {"Rate", "Taxable", "Total"} else "center"
            if label == "Period":
                align = "center"
            _draw_cell_text(canvas, x, y, width, height, value, size=6.8, color=TEXT, align=align)
        x += width


def _draw_description_cell(canvas: Canvas, x: float, top: float, width: float, height: float, description: dict[str, list[str] | str]) -> None:
    pad_x = CELL_PAD_X
    current_y = top - CELL_PAD_Y - 2
    inner_width = width - (pad_x * 2)

    canvas.saveState()
    path = canvas.beginPath()
    path.rect(x + 1, top - height + 1, width - 2, height - 2)
    canvas.clipPath(path, stroke=0, fill=0)

    title_lines = _wrap_text(str(description["title"]), inner_width, font="Helvetica-Bold", size=7.3)[:3]
    for line in title_lines:
        _draw_text(canvas, line, x + pad_x, current_y, font="Helvetica-Bold", size=7.3, color=TEXT)
        current_y -= 7.8

    for detail in description["details"]:
        detail_lines = _wrap_text(detail, inner_width, font="Helvetica", size=6.5)[:2]
        for line in detail_lines:
            _draw_text(canvas, line, x + pad_x, current_y, size=6.5, color=MUTED)
            current_y -= 7

    canvas.restoreState()


def _line_row_height(row: dict, columns: list[tuple[str, float]]) -> float:
    desc_width = next(width for label, width in columns if label == "Description") - (CELL_PAD_X * 2)
    desc = row["description"]
    title_count = min(3, len(_wrap_text(str(desc["title"]), desc_width, font="Helvetica-Bold", size=7.3)))
    detail_count = 0
    for detail in desc["details"]:
        detail_count += min(2, len(_wrap_text(detail, desc_width, font="Helvetica", size=6.5)))
    desc_height = CELL_PAD_Y + 3 + (title_count * 7.8) + (detail_count * 7) + CELL_PAD_Y

    value_heights = []
    for label, width in columns:
        if label == "Description":
            continue
        value = row["values"].get(label, "")
        line_count = max(1, len(_wrap_text(value, width - (CELL_PAD_X * 2), font="Helvetica", size=6.8)))
        value_heights.append(CELL_PAD_Y + (line_count * 7.4) + CELL_PAD_Y)

    return max(15 * mm, desc_height + 2, *(value_heights or [0]))


def _line_row(line, invoice: Invoice, index: int, *, include_gst: bool) -> dict:
    if line is None:
        values = {"#": str(index), "Period": "", "HSN/SAC": "", "Qty": "", "Rate": "", "Taxable": "", "Total": ""}
        if include_gst:
            values["GST %"] = ""
        return {
            "description": {"title": "No line items available", "details": []},
            "values": values,
        }

    values = {
        "#": str(index),
        "Period": _line_period(line, invoice),
        "HSN/SAC": _clean(line.hsn_code or line.sac_code),
        "Qty": _decimal_label(line.quantity),
        "Rate": format_money(line.unit_price),
        "Taxable": format_money(line.taxable_value),
        "Total": format_money(line.line_total),
    }
    if include_gst:
        values["GST %"] = _percent(line.gst_rate)
    return {
        "description": _line_description(line),
        "values": values,
    }


def _summary_section_height(invoice: Invoice) -> float:
    if not _invoice_has_gst(invoice):
        return 42 * mm
    tax_rows = _build_tax_summary(invoice)
    tax_height = 15 * mm + (len(tax_rows) * 7 * mm)
    return max(35 * mm, tax_height) + 14 * mm


def _draw_financial_summary(canvas: Canvas, invoice: Invoice, y: float) -> float:
    include_gst = _invoice_has_gst(invoice)
    tax_rows = _build_tax_summary(invoice)
    gap = 5 * mm
    tax_width = TABLE_WIDTH * 0.64 if include_gst else TABLE_WIDTH * 0.52
    totals_width = TABLE_WIDTH - tax_width - gap
    tax_height = max(35 * mm, 15 * mm + (len(tax_rows) * 7 * mm)) if include_gst else 30 * mm
    totals_height = 39 * mm
    section_height = max(tax_height, totals_height)

    if include_gst:
        _draw_tax_summary(canvas, MARGIN_X, y, tax_width, tax_height, tax_rows)
    else:
        _draw_non_gst_note(canvas, MARGIN_X, y, tax_width, tax_height)
    _draw_totals_card(canvas, MARGIN_X + tax_width + gap, y, totals_width, totals_height, invoice, include_gst=include_gst)

    y -= section_height + 4 * mm
    amount_height = 10 * mm
    _draw_amount_words_strip(canvas, invoice, y, amount_height)
    return y - amount_height - 4 * mm


def _draw_amount_words_strip(canvas: Canvas, invoice: Invoice, y: float, height: float) -> None:
    _draw_card(canvas, MARGIN_X, y, TABLE_WIDTH, height, "", fill=FOREST_SOFT)
    _draw_text(canvas, "Amount in Words", MARGIN_X + 4 * mm, y - 6.3 * mm, font="Helvetica-Bold", size=6.8, color=FOREST_DARK)
    _draw_wrapped_text(
        canvas,
        amount_to_words(invoice.grand_total),
        MARGIN_X + 38 * mm,
        y - 6.3 * mm,
        TABLE_WIDTH - 42 * mm,
        font="Helvetica-Bold",
        size=7.4,
        leading=8,
        color=FOREST_DARK,
        max_lines=2,
    )


def _draw_tax_summary(canvas: Canvas, x: float, y: float, width: float, height: float, tax_rows: list[dict[str, Decimal | str]]) -> None:
    _draw_card(canvas, x, y, width, height, "Tax Summary")
    columns = [
        ("GST Rate", 38),
        ("Taxable", 58),
        ("CGST", 48),
        ("SGST", 48),
        ("IGST", 48),
        ("Tax", width - 38 - 58 - 48 - 48 - 48 - 8),
    ]
    row_y = y - 11 * mm
    row_y = _draw_compact_table_header(canvas, x + 4, row_y, columns)
    for tax_row in tax_rows:
        row_values = [
            f"{tax_row['rate']}%" if tax_row["rate"] != "" else "0%",
            format_money(tax_row["taxable"]),
            format_money(tax_row["cgst"]),
            format_money(tax_row["sgst"]),
            format_money(tax_row["igst"]),
            format_money(tax_row["total_tax"]),
        ]
        _draw_compact_table_row(canvas, x + 4, row_y, columns, row_values)
        row_y -= 7 * mm


def _draw_non_gst_note(canvas: Canvas, x: float, y: float, width: float, height: float) -> None:
    _draw_card(canvas, x, y, width, height, "Tax Status")
    _draw_wrapped_text(
        canvas,
        "Non-GST bill. Supplier GST registration is not configured, so GST is not applied.",
        x + 4 * mm,
        y - 12 * mm,
        width - 8 * mm,
        size=7.3,
        leading=8,
        color=MUTED,
    )


def _draw_totals_card(canvas: Canvas, x: float, y: float, width: float, height: float, invoice: Invoice, *, include_gst: bool) -> None:
    _draw_card(canvas, x, y, width, height, "Totals", fill=MINT)
    rows = [
        ("Subtotal", invoice.subtotal),
        ("Discount", invoice.discount_total),
    ]
    if include_gst:
        rows.extend(
            [
                ("CGST", invoice.cgst_total),
                ("SGST", invoice.sgst_total),
                ("IGST", invoice.igst_total),
            ]
        )
    row_y = y - 10.5 * mm
    for label, value in rows:
        _draw_text(canvas, label, x + 4.5 * mm, row_y, size=6.7, color=MUTED)
        _draw_text(canvas, format_money(value), x + width - 4.5 * mm, row_y, size=6.7, color=TEXT, align="right")
        row_y -= 4 * mm

    grand_top = y - height + 12 * mm
    canvas.setFillColor(FOREST_SOFT)
    canvas.setStrokeColor(FOREST)
    canvas.setLineWidth(0.8)
    canvas.roundRect(x + 3.2 * mm, grand_top - 11 * mm, width - 6.4 * mm, 11 * mm, 3, stroke=1, fill=1)
    _draw_text(canvas, "Grand Total", x + 5.5 * mm, grand_top - 7 * mm, font="Helvetica-Bold", size=8.8, color=FOREST_DARK)
    _draw_text(canvas, format_money(invoice.grand_total), x + width - 5.5 * mm, grand_top - 7 * mm, font="Helvetica-Bold", size=9.8, color=FOREST_DARK, align="right")


def _draw_payment_terms_and_signature(canvas: Canvas, invoice: Invoice, y: float) -> None:
    gap = 5 * mm
    width = (TABLE_WIDTH - gap) / 2
    height = 32 * mm
    payment_rows = _build_bank_detail_rows(invoice)
    terms = [
        "E. & O.E.",
        "Subject to local jurisdiction.",
        "Interest may apply on overdue balances.",
        "This invoice is generated from confirmed OMMS bookings.",
    ]
    _draw_bank_details_card(canvas, MARGIN_X, y, width, height, payment_rows)
    _draw_text_card(canvas, MARGIN_X + width + gap, y, width, height, "Terms & Conditions", terms)

    sign_y = y - height - 6.5 * mm
    sign_x = PAGE_WIDTH - MARGIN_X
    canvas.setStrokeColor(BORDER_DARK)
    canvas.setLineWidth(0.7)
    canvas.line(sign_x - 56 * mm, sign_y, sign_x, sign_y)
    _draw_text(canvas, "Authorised Signatory", sign_x, sign_y - 4.5 * mm, font="Helvetica-Bold", size=7.8, color=FOREST_DARK, align="right")
    _draw_text(canvas, f"For {_company_display_name(invoice, _get_company_profile())}", sign_x, sign_y - 8.5 * mm, size=7.2, color=MUTED, align="right")


def _draw_bank_details_card(canvas: Canvas, x: float, y: float, width: float, height: float, rows: list[tuple[str, str]]) -> None:
    _draw_card(canvas, x, y, width, height, "Bank / Payment Details")
    content_y = y - 11 * mm
    if not rows:
        _draw_wrapped_text(canvas, "Bank details will be shared separately.", x + 4 * mm, content_y, width - 8 * mm, size=7.2, leading=7.8, color=TEXT)
        return
    label_width = 31 * mm
    for label, value in rows:
        _draw_text(canvas, label, x + 4 * mm, content_y, font="Helvetica-Bold", size=6.7, color=MUTED)
        used = _draw_wrapped_text(canvas, value, x + 4 * mm + label_width, content_y, width - 8 * mm - label_width, size=7, leading=7.6, color=TEXT, max_lines=2)
        content_y -= max(used, 1) * 3.9 * mm
        if content_y < y - height + 5 * mm:
            break


def _draw_text_card(canvas: Canvas, x: float, y: float, width: float, height: float, title: str, lines: list[str]) -> None:
    _draw_card(canvas, x, y, width, height, title)
    content_y = y - 11 * mm
    if not lines:
        lines = ["Details will be shared separately."]
    for line in lines:
        used = _draw_wrapped_text(canvas, line, x + 4 * mm, content_y, width - 8 * mm, size=7, leading=7.6, color=TEXT, max_lines=2)
        content_y -= max(used, 1) * 3.8 * mm
        if content_y < y - height + 5 * mm:
            break


def _draw_card(canvas: Canvas, x: float, y: float, width: float, height: float, title: str, *, fill=WHITE) -> None:
    canvas.setFillColor(fill)
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.8)
    canvas.roundRect(x, y - height, width, height, 6, stroke=1, fill=1)
    _draw_text(canvas, title, x + 4 * mm, y - 5 * mm, font="Helvetica-Bold", size=6.4, color=FOREST_DARK)


def _draw_cell_box(canvas: Canvas, x: float, y: float, width: float, height: float, *, fill=WHITE, stroke=BORDER) -> None:
    canvas.setFillColor(fill)
    canvas.setStrokeColor(stroke)
    canvas.setLineWidth(0.45)
    canvas.rect(x, y - height, width, height, stroke=1, fill=1)


def _draw_cell_text(
    canvas: Canvas,
    x: float,
    top: float,
    width: float,
    height: float,
    text: str,
    *,
    font: str = "Helvetica",
    size: float = 7,
    color=TEXT,
    align: str = "left",
) -> None:
    inner_width = max(width - (CELL_PAD_X * 2), 2)
    lines = _wrap_text(text, inner_width, font=font, size=size)
    leading = size + 1.2
    total_height = len(lines) * leading
    start_y = top - ((height - total_height) / 2) - size
    if align == "left":
        draw_x = x + CELL_PAD_X
    elif align == "right":
        draw_x = x + width - CELL_PAD_X
    else:
        draw_x = x + (width / 2)

    canvas.saveState()
    path = canvas.beginPath()
    path.rect(x + 1, top - height + 1, width - 2, height - 2)
    canvas.clipPath(path, stroke=0, fill=0)
    for offset, line in enumerate(lines):
        _draw_text(canvas, line, draw_x, start_y - (offset * leading), font=font, size=size, color=color, align=align)
    canvas.restoreState()


def _draw_compact_table_header(canvas: Canvas, x: float, y: float, columns: list[tuple[str, float]]) -> float:
    height = 6.5 * mm
    current_x = x
    for label, width in columns:
        _draw_cell_box(canvas, current_x, y, width, height, fill=FOREST_SOFT, stroke=BORDER)
        _draw_cell_text(canvas, current_x, y, width, height, label, font="Helvetica-Bold", size=5.9, color=FOREST_DARK, align="center")
        current_x += width
    return y - height


def _draw_compact_table_row(canvas: Canvas, x: float, y: float, columns: list[tuple[str, float]], values: list[str]) -> None:
    height = 7 * mm
    current_x = x
    for index, ((_, width), value) in enumerate(zip(columns, values)):
        _draw_cell_box(canvas, current_x, y, width, height, fill=WHITE, stroke=BORDER)
        align = "center" if index == 0 else "right"
        _draw_cell_text(canvas, current_x, y, width, height, value, size=6.1, color=TEXT, align=align)
        current_x += width


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
    if not value:
        return
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
    lines = _wrap_text(text, width, font=font, size=size)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _truncate_to_width(lines[-1] + "...", width, font, size)
    for offset, line in enumerate(lines):
        draw_x = x if align != "right" else x + width
        _draw_text(canvas, line, draw_x, y - (offset * leading), font=font, size=size, color=color, align=align)
    return len(lines)


def _wrap_text(text: str, width: float, *, font: str, size: float) -> list[str]:
    value = _clean(text)
    if not value:
        return []
    result: list[str] = []
    for paragraph in str(value).splitlines() or [str(value)]:
        words = paragraph.split()
        if not words:
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
    return result


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


def _draw_footer(canvas: Canvas, page_number: int, total_pages: int | None = None) -> None:
    y = 8 * mm
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN_X, y + 4 * mm, PAGE_WIDTH - MARGIN_X, y + 4 * mm)
    page_label = f"Page {page_number} of {total_pages}" if total_pages else f"Page {page_number}"
    _draw_text(canvas, f"Generated by OMMS | {page_label}", MARGIN_X, y, size=6.7, color=MUTED)


def _supplier_card(invoice: Invoice) -> dict[str, list[str] | str]:
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
    contact = _join(
        f"Email: {invoice.supplier_contact_email}" if invoice.supplier_contact_email else "",
        f"Phone: {invoice.supplier_contact_phone}" if invoice.supplier_contact_phone else "",
        sep="  |  ",
    )
    lines = [
        legal_name,
        f"Address: {address}" if address else "",
        f"GSTIN: {invoice.supplier_gstin}" if invoice.supplier_gstin else "",
        f"State Code: {invoice.supplier_state_code}" if invoice.supplier_state_code else "",
        contact,
    ]
    return {"name": name, "lines": [line for line in lines if _clean(line)]}


def _client_card(invoice: Invoice) -> dict[str, list[str] | str]:
    address = _join(
        invoice.client_billing_address_line_1,
        invoice.client_billing_address_line_2,
        invoice.client_billing_city,
        invoice.client_billing_state,
        invoice.client_billing_postal_code,
        invoice.client_billing_country,
    )
    lines = [
        f"Address: {address}" if address else "",
        f"GSTIN: {invoice.client_gstin}" if invoice.client_gstin else "",
        f"State Code: {invoice.client_billing_state_code}" if invoice.client_billing_state_code else "",
    ]
    return {"name": invoice.client_legal_name or "Client", "lines": [line for line in lines if _clean(line)]}


def _line_description(line) -> dict[str, list[str] | str]:
    site = _clean(line.site_name or _line_booking_site_name(line))
    media_unit = _clean(line.media_unit_label or _line_booking_unit_label(line))
    title = _clean_service_title(line.item_description or line.description or "Outdoor media display service", site, media_unit)
    details = []
    if site:
        details.append(f"Site: {site}")
    if media_unit:
        details.append(f"Media Unit: {media_unit}")
    return {"title": title, "details": details}


def _clean_service_title(title: str, site: str = "", media_unit: str = "") -> str:
    value = _clean(title) or "Outdoor media display service"
    for token in [site, media_unit]:
        if token:
            value = re.sub(rf"\s*(?:[-/|])?\s*{re.escape(token)}\s*", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" -/|")
    return value or "Outdoor media display service"


def _line_booking_site_name(line) -> str:
    booking = getattr(line, "booking", None)
    media_unit = getattr(booking, "media_unit", None)
    site = getattr(media_unit, "site", None)
    return getattr(site, "name", "") or ""


def _line_booking_unit_label(line) -> str:
    booking = getattr(line, "booking", None)
    media_unit = getattr(booking, "media_unit", None)
    return getattr(media_unit, "unit_code", "") or ""


def _line_period(line, invoice: Invoice) -> str:
    start = line.booking_start_date or getattr(invoice.campaign, "start_date", None)
    end = line.booking_end_date or getattr(invoice.campaign, "end_date", None)
    if start and end:
        return f"{_date(start)} to {_date(end)}"
    return ""


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
    return rows or [{"rate": "", "taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO, "total_tax": ZERO}]


def _invoice_has_gst(invoice: Invoice) -> bool:
    if invoice.supplier_gstin or quantize_money(invoice.total_tax) > ZERO:
        return True
    return any(quantize_money(line.gst_rate) > ZERO for line in invoice.lines.all())


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
        site = _clean(first_line.site_name or _line_booking_site_name(first_line))
        unit = _clean(first_line.media_unit_label or _line_booking_unit_label(first_line))
        return _clean_service_title(first_line.item_description or first_line.description, site, unit)
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
    profile = _get_company_profile()
    if profile and profile.bank_details:
        return profile.bank_details.strip()
    return "Bank details will be shared separately."


def _build_bank_detail_rows(invoice: Invoice) -> list[tuple[str, str]]:
    raw_details = _build_account_details(invoice)
    if raw_details == "Bank details will be shared separately.":
        return []

    rows = []
    for line in _split_lines(raw_details):
        label, separator, value = line.partition(":")
        if not separator and " - " in line:
            label, separator, value = line.partition(" - ")
        if not separator:
            rows.append(("Details", line))
            continue
        normalized_label = _normalize_bank_label(label)
        normalized_value = _clean(value)
        if normalized_value:
            rows.append((normalized_label, normalized_value))
    return rows


def _normalize_bank_label(label: str) -> str:
    value = _clean(label).lower()
    if "holder" in value:
        return "Account Holder"
    if value in {"a/c", "ac"}:
        return "Account Holder"
    if "ifsc" in value:
        return "IFSC"
    if "account" in value or "a/c" in value or "a/c no" in value:
        return "Account Number"
    if "branch" in value:
        return "Branch"
    if "bank" in value:
        return "Bank"
    return _clean(label).title()


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


def _get_company_profile():
    try:
        from apps.setup.models import CompanyProfile

        return CompanyProfile.objects.filter(singleton_key=1).first()
    except Exception:
        return None


def _company_display_name(invoice: Invoice, profile=None) -> str:
    return (
        invoice.supplier_trade_name
        or invoice.supplier_legal_name
        or getattr(profile, "company_name", "")
        or getattr(profile, "legal_name", "")
        or "OMMS"
    )


def _campaign_label(invoice: Invoice) -> str:
    if invoice.campaign_id:
        code = getattr(invoice.campaign, "code", "")
        name = getattr(invoice.campaign, "name", "")
        return _join(name, code, sep=" / ")
    return ""


def _join(*parts, sep: str = ", ") -> str:
    return sep.join(_clean(part) for part in parts if _clean(part))


def _join_state(state, code) -> str:
    state_value = _clean(state)
    code_value = _clean(code)
    if state_value and code_value:
        return f"{state_value} ({code_value})"
    return state_value or code_value


def _split_lines(value: str) -> list[str]:
    return [_clean(line) for line in str(value or "").splitlines() if _clean(line)]


def _date(value, *, required: bool = False) -> str:
    if not value:
        return ""
    return value.strftime("%d-%m-%Y")


def _percent(value) -> str:
    return f"{format(quantize_money(value), 'g')}%"


def _decimal_label(value) -> str:
    return format(quantize_money(value), "g")


def _required(value) -> str:
    return _clean(value)


def _clean(value, default: str = "") -> str:
    if value in ("", None):
        value = default
    return re.sub(r"\s+", " ", str(value)).strip()
