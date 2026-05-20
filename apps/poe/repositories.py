from core.repositories import BaseRepository
from core.roles import CLIENT
from apps.tenants.services import is_platform_super_admin, scope_queryset_to_tenant_path

from .models import ProofOfExecution, ProofOfExecutionMedia, ProofOfExecutionVerificationLog


class ProofOfExecutionRepository(BaseRepository):
    model = ProofOfExecution
    select_related = ("booking", "booking__campaign", "booking__media_unit", "booking__media_unit__site", "checked_by")
    prefetch_related = ("media_items", "verification_logs")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "booking__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(booking__campaign__client=user)
        return queryset.order_by("-created_at")


class ProofOfExecutionMediaRepository(BaseRepository):
    model = ProofOfExecutionMedia
    select_related = ("poe_record", "captured_by")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "poe_record__booking__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(poe_record__booking__campaign__client=user)
        return queryset.order_by("-created_at")


class ProofOfExecutionVerificationLogRepository(BaseRepository):
    model = ProofOfExecutionVerificationLog
    select_related = ("poe_record", "verified_by")

    def scope_queryset(self, queryset, user=None):
        queryset = scope_queryset_to_tenant_path(queryset, user, "poe_record__booking__campaign__tenant")
        if user and getattr(user, "role", None) == CLIENT and not is_platform_super_admin(user):
            queryset = queryset.filter(poe_record__booking__campaign__client=user)
        return queryset.order_by("-created_at")
