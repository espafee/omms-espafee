from core.repositories import BaseRepository
from core.roles import CLIENT
from apps.tenants.services import is_platform_super_admin, scope_queryset_to_tenant_path

from .models import CampaignEstimate, CampaignEstimateLine, CreditNote, Invoice, InvoiceEvent, InvoiceLine, Payment, SupplierProfile


class SupplierProfileRepository(BaseRepository):
    model = SupplierProfile

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user)
        return queryset.order_by("legal_name")


class InvoiceRepository(BaseRepository):
    model = Invoice
    select_related = ("campaign", "campaign__client", "supplier_profile", "issued_by", "cancelled_by")
    prefetch_related = ("lines", "payments__recorded_by", "credit_notes__created_by", "events__actor")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(campaign__client=user)
        return queryset.order_by("-created_at")


class CampaignEstimateRepository(BaseRepository):
    model = CampaignEstimate
    select_related = ("client", "campaign", "created_by")
    prefetch_related = ("lines",)

    def scope_queryset(self, queryset, user=None):
        if not is_platform_super_admin(user):
            queryset = queryset.filter(client__tenant=getattr(user, "tenant", None))
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(client=user)
        return queryset.order_by("-created_at")


class CampaignEstimateLineRepository(BaseRepository):
    model = CampaignEstimateLine
    select_related = ("estimate", "media_unit", "media_unit__site")

    def scope_queryset(self, queryset, user=None):
        if not is_platform_super_admin(user):
            queryset = queryset.filter(estimate__client__tenant=getattr(user, "tenant", None))
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(estimate__client=user)
        return queryset.order_by("id")


class InvoiceLineRepository(BaseRepository):
    model = InvoiceLine
    select_related = ("invoice", "booking")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "invoice__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("line_number", "id")


class PaymentRepository(BaseRepository):
    model = Payment
    select_related = ("invoice", "recorded_by")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "invoice__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("-created_at")


class CreditNoteRepository(BaseRepository):
    model = CreditNote
    select_related = ("invoice", "created_by")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "invoice__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("-credit_date", "-created_at")


class InvoiceEventRepository(BaseRepository):
    model = InvoiceEvent
    select_related = ("invoice", "actor")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "invoice__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(invoice__campaign__client=user)
        return queryset.order_by("-created_at", "-id")
