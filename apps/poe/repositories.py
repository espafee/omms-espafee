from core.repositories import BaseRepository
from core.roles import CLIENT

from .models import ProofOfExecution, ProofOfExecutionMedia, ProofOfExecutionVerificationLog


class ProofOfExecutionRepository(BaseRepository):
    model = ProofOfExecution
    select_related = ("booking", "booking__campaign", "booking__media_unit", "booking__media_unit__site", "checked_by")
    prefetch_related = ("media_items", "verification_logs")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(booking__campaign__client=user)
        return queryset.order_by("-created_at")


class ProofOfExecutionMediaRepository(BaseRepository):
    model = ProofOfExecutionMedia
    select_related = ("poe_record", "captured_by")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(poe_record__booking__campaign__client=user)
        return queryset.order_by("-created_at")


class ProofOfExecutionVerificationLogRepository(BaseRepository):
    model = ProofOfExecutionVerificationLog
    select_related = ("poe_record", "verified_by")

    def scope_queryset(self, queryset, user=None):
        if user and getattr(user, "role", None) == CLIENT:
            queryset = queryset.filter(poe_record__booking__campaign__client=user)
        return queryset.order_by("-created_at")
