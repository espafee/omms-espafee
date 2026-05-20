from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.bookings.models import Booking
from apps.bookings.models import Assignment
from apps.poe.models import ProofOfExecution
from apps.poe.services import ProofOfExecutionMediaService, ProofOfExecutionService
from apps.tenants.services import is_platform_super_admin, require_same_tenant, scope_queryset_to_tenant_path
from core.roles import ADMIN


ADMIN_MOBILE_ROLES = {ADMIN, "super_admin", "owner"}


def is_admin_like_user(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "role", None) in ADMIN_MOBILE_ROLES
        )
    )


def user_can_access_booking(user, booking: Booking) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_admin_like_user(user):
        if is_platform_super_admin(user):
            return True
        try:
            require_same_tenant(user, booking.campaign.tenant, message="You do not have permission to access this booking.")
        except PermissionDenied:
            return False
        return True
    return booking.assignments.filter(
        user=user,
        status__in=[Assignment.Status.PENDING, Assignment.Status.COMPLETED],
    ).exists()


class MobileWorkService:
    @staticmethod
    def get_assigned_work_queryset(user):
        queryset = (
            Booking.objects.select_related(
                "campaign",
                "media_unit",
                "media_unit__site",
            )
            .prefetch_related("poe_records")
            .prefetch_related("assignments")
            .exclude(status=Booking.Status.CANCELLED)
            .order_by("start_date", "id")
        )
        queryset = scope_queryset_to_tenant_path(queryset, user, "campaign__tenant")
        if is_admin_like_user(user):
            return queryset
        return queryset.filter(
            assignments__user=user,
            assignments__status__in=[Assignment.Status.PENDING, Assignment.Status.COMPLETED],
        ).distinct()

    @classmethod
    def get_assigned_work(cls, user):
        items = []
        for booking in cls.get_assigned_work_queryset(user):
            site = booking.media_unit.site
            latest_poe = booking.poe_records.order_by("-created_at").first()
            items.append(
                {
                    "booking_id": booking.id,
                    "campaign_id": booking.campaign_id,
                    "campaign_name": booking.campaign.name,
                    "site_id": site.id,
                    "site_name": site.name,
                    "unit_id": booking.media_unit_id,
                    "unit_name": booking.media_unit.unit_code,
                    "location": site.city or site.address,
                    "latitude": site.latitude,
                    "longitude": site.longitude,
                    "booking_start": booking.start_date,
                    "booking_end": booking.end_date,
                    "poe_status": latest_poe.verification_status if latest_poe else "pending",
                }
            )
        return items

    @staticmethod
    def get_booking_for_submit(user, booking_id: int) -> Booking:
        try:
            booking = (
                Booking.objects.select_related("campaign", "media_unit", "media_unit__site")
                .prefetch_related("assignments")
                .get(pk=booking_id)
            )
        except Booking.DoesNotExist as exc:
            raise ValidationError({"booking_id": ["Booking does not exist."]}) from exc

        if not user_can_access_booking(user, booking):
            raise PermissionDenied("You do not have permission to submit POE for this booking.")
        return booking

    @classmethod
    @transaction.atomic
    def submit_poe(cls, *, user, booking_id, image, latitude, longitude, captured_at, notes=""):
        booking = cls.get_booking_for_submit(user, booking_id)
        captured_at = captured_at or timezone.now()
        poe_record = ProofOfExecutionService().create(
            actor=user,
            booking=booking,
            executed_on=timezone.localtime(captured_at).date(),
            captured_at=captured_at,
            latitude=latitude,
            longitude=longitude,
            notes=notes,
        )
        ProofOfExecutionMediaService().create(
            actor=user,
            poe_record=poe_record,
            image=image,
            captured_at=captured_at,
            note=notes,
        )
        verification = ProofOfExecutionService().verify_record(poe_record, actor=user)
        poe_record.refresh_from_db()
        return {
            "detail": "POE submitted successfully.",
            "poe_id": poe_record.id,
            "status": verification["verification_status"],
            "distance_meters": verification["distance_meters"],
        }
