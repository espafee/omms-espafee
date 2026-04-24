from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "campaign", "issue_date", "due_date", "total_amount", "status")
    list_filter = ("status", "issue_date", "due_date")
    search_fields = ("invoice_number", "campaign__name", "campaign__code")
    inlines = [InvoiceLineInline, PaymentInline]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("invoice", "description", "quantity", "unit_price", "line_total")
    search_fields = ("description", "invoice__invoice_number")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "payment_date", "amount", "method", "reference_number")
    list_filter = ("method", "payment_date")
    search_fields = ("invoice__invoice_number", "reference_number")
