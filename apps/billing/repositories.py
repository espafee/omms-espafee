from core.repositories import BaseRepository
from core.roles import CLIENT

from .models import CampaignEstimate, CampaignEstimateLine, Invoice, InvoiceLine, Payment, SupplierProfile


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


class CampaignEstimateRepository(BaseRepository):
    model = CampaignEstimate
    select_related = ("client", "campaign", "created_by")
    prefetch_related = ("lines",)

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(client=user)
        return queryset.order_by("-created_at")


class CampaignEstimateLineRepository(BaseRepository):
    model = CampaignEstimateLine
    select_related = ("estimate", "media_unit", "media_unit__site")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(estimate__client=user)
        return queryset.order_by("id")


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
