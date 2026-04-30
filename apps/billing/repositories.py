from core.repositories import BaseRepository
from core.roles import CLIENT

from .models import Invoice, InvoiceLine, Payment, SupplierProfile


class SupplierProfileRepository(BaseRepository):
    model = SupplierProfile

    def scope_queryset(self, queryset, user=None):
        return queryset.order_by("legal_name")


class InvoiceRepository(BaseRepository):
    model = Invoice
    select_related = ("campaign", "campaign__client", "supplier_profile", "issued_by", "cancelled_by")
    prefetch_related = ("lines", "payments")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(campaign__client=user)
        return queryset.order_by("-created_at")


class InvoiceLineRepository(BaseRepository):
    model = InvoiceLine
    select_related = ("invoice", "booking")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("line_number", "id")


class PaymentRepository(BaseRepository):
    model = Payment
    select_related = ("invoice",)

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("-created_at")
