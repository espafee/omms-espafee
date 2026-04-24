from core.repositories import BaseRepository
from core.roles import CLIENT

from .models import Invoice, InvoiceLine, Payment


class InvoiceRepository(BaseRepository):
    model = Invoice
    select_related = ("campaign", "campaign__client")
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
        return queryset.order_by("-created_at")


class PaymentRepository(BaseRepository):
    model = Payment
    select_related = ("invoice",)

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("-created_at")
