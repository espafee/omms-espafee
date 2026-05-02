from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.bookings.models import Assignment, Booking
from apps.campaigns.models import Campaign
from apps.poe.models import ProofOfExecution
from core.images import build_public_media_url


FAILED_STATUS = "failed"
STATUS_FILTER_MAP = {
    "pending": ProofOfExecution.VerificationStatus.PENDING,
    "verified": ProofOfExecution.VerificationStatus.VERIFIED,
    "suspicious": ProofOfExecution.VerificationStatus.SUSPICIOUS,
    FAILED_STATUS: ProofOfExecution.VerificationStatus.REJECTED,
}


def _base_booking_queryset():
    return (
        Booking.objects.select_related("campaign", "campaign__client", "media_unit", "media_unit__site")
        .prefetch_related("assignments__user", "poe_records__media_items", "poe_records__verification_logs")
        .exclude(status=Booking.Status.CANCELLED)
    )


def _active_campaign_queryset(today):
    return (
        Campaign.objects.select_related("client")
        .filter(Q(status=Campaign.Status.ACTIVE) | Q(start_date__lte=today, end_date__gte=today))
        .distinct()
        .order_by("end_date", "id")
    )


def _latest_poe(booking):
    return booking.poe_records.order_by("-captured_at", "-created_at", "-id").first()


def _has_verified_poe(booking) -> bool:
    return booking.poe_records.filter(verification_status=ProofOfExecution.VerificationStatus.VERIFIED).exists()


def _is_poe_pending(booking) -> bool:
    latest = _latest_poe(booking)
    return latest is None or latest.verification_status == ProofOfExecution.VerificationStatus.PENDING


def _has_any_poe(booking) -> bool:
    return booking.poe_records.exists()


def _active_assignment(booking):
    return booking.assignments.select_related("user").filter(status=Assignment.Status.PENDING).first()


def _overdue_assignment_bookings(today):
    return [
        booking
        for booking in _base_booking_queryset().filter(
            assignments__status=Assignment.Status.PENDING,
            start_date__lte=today,
        ).distinct()
        if not _has_any_poe(booking)
    ]


def _assignee_label(booking) -> str:
    assignment = booking.assignments.select_related("user").exclude(status=Assignment.Status.CANCELLED).first()
    if not assignment:
        return ""
    return assignment.user.get_full_name() or assignment.user.email


def _client_label(campaign) -> str:
    return campaign.client.organization_name or campaign.client.get_full_name() or campaign.client.email


def _activity_item(booking, *, due_date, status):
    site = booking.media_unit.site
    return {
        "booking_id": booking.id,
        "campaign_name": booking.campaign.name,
        "site_name": site.name,
        "unit_name": booking.media_unit.unit_code,
        "assigned_to": _assignee_label(booking),
        "due_date": due_date,
        "status": status,
    }


def _latest_distance(poe_record):
    latest_log = poe_record.verification_logs.order_by("-created_at", "-id").first()
    return latest_log.distance_meters if latest_log else None


def _latest_image_url(poe_record, request=None):
    media = poe_record.media_items.order_by("-captured_at", "-created_at", "-id").first()
    if not media:
        return None
    if media.media_url:
        return media.media_url
    return build_public_media_url(media.image, request=request)


class MobileAdminOperationsService:
    @staticmethod
    def get_overview():
        today = timezone.localdate()
        bookings = _base_booking_queryset()
        return {
            "active_campaigns": _active_campaign_queryset(today).count(),
            "poe_pending": sum(1 for booking in bookings if _is_poe_pending(booking)),
            "poe_completed_today": ProofOfExecution.objects.filter(
                captured_at__date=today,
                verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
            ).count(),
            "suspicious_poe": ProofOfExecution.objects.filter(
                verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS
            ).count(),
            "bookings_starting_today": Booking.objects.filter(start_date=today).exclude(status=Booking.Status.CANCELLED).count(),
            "bookings_ending_today": Booking.objects.filter(end_date=today).exclude(status=Booking.Status.CANCELLED).count(),
        }

    @staticmethod
    def get_running_campaigns():
        today = timezone.localdate()
        items = []
        for campaign in _active_campaign_queryset(today).prefetch_related("bookings__poe_records"):
            campaign_bookings = [booking for booking in campaign.bookings.all() if booking.status != Booking.Status.CANCELLED]
            total_units = len({booking.media_unit_id for booking in campaign_bookings})
            poe_completed = sum(1 for booking in campaign_bookings if _has_verified_poe(booking))
            poe_pending = max(total_units - poe_completed, 0)
            progress = round((poe_completed / total_units) * 100) if total_units else 0
            items.append(
                {
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "client_name": _client_label(campaign),
                    "start_date": campaign.start_date,
                    "end_date": campaign.end_date,
                    "total_units": total_units,
                    "poe_completed": poe_completed,
                    "poe_pending": poe_pending,
                    "poe_progress_percent": progress,
                    "status": campaign.status,
                }
            )
        return items

    @staticmethod
    def get_poe_tracker(*, status_filter=None, request=None):
        queryset = ProofOfExecution.objects.select_related(
            "booking",
            "booking__campaign",
            "booking__media_unit",
            "booking__media_unit__site",
        ).prefetch_related("booking__assignments__user", "media_items", "verification_logs")

        mapped_status = STATUS_FILTER_MAP.get(status_filter or "")
        if mapped_status:
            queryset = queryset.filter(verification_status=mapped_status)

        items = []
        for poe_record in queryset.order_by("-captured_at", "-created_at", "-id"):
            booking = poe_record.booking
            site = booking.media_unit.site
            status_value = FAILED_STATUS if poe_record.verification_status == ProofOfExecution.VerificationStatus.REJECTED else poe_record.verification_status
            items.append(
                {
                    "poe_id": poe_record.id,
                    "booking_id": booking.id,
                    "campaign_name": booking.campaign.name,
                    "site_name": site.name,
                    "unit_name": booking.media_unit.unit_code,
                    "field_staff": _assignee_label(booking),
                    "submitted_at": poe_record.captured_at,
                    "status": status_value,
                    "distance_meters": _latest_distance(poe_record),
                    "image_url": _latest_image_url(poe_record, request=request),
                }
            )
        return items

    @staticmethod
    def get_daily_activity():
        today = timezone.localdate()
        active_bookings = _base_booking_queryset().filter(start_date__lte=today, end_date__gte=today)
        overdue_assignment_ids = {booking.id for booking in _overdue_assignment_bookings(today)}
        return {
            "date": today,
            "installations_due_today": [
                _activity_item(booking, due_date=booking.start_date, status="installation_due")
                for booking in _base_booking_queryset().filter(start_date=today)
            ],
            "poe_pending_today": [
                _activity_item(booking, due_date=today, status="poe_pending")
                for booking in active_bookings
                if _is_poe_pending(booking)
            ],
            "overdue_items": [
                _activity_item(booking, due_date=booking.end_date, status="overdue")
                for booking in _base_booking_queryset().filter(end_date__lt=today)
                if not _has_verified_poe(booking) and booking.id not in overdue_assignment_ids
            ]
            + [
                _activity_item(booking, due_date=booking.start_date, status="overdue")
                for booking in _overdue_assignment_bookings(today)
            ],
        }

    @staticmethod
    def get_alerts():
        today = timezone.localdate()
        now = timezone.now()
        alerts = []

        for booking in _base_booking_queryset().filter(end_date__lt=today):
            if not _has_verified_poe(booking):
                alerts.append(
                    {
                        "type": "overdue_poe",
                        "severity": "warning",
                        "title": "POE overdue",
                        "message": f"{booking.campaign.name} at {booking.media_unit.site.name} is overdue.",
                        "related_id": booking.id,
                        "created_at": now,
                    }
                )

        for booking in _overdue_assignment_bookings(today):
            assignment = _active_assignment(booking)
            assigned_to = assignment.user.get_full_name() or assignment.user.email if assignment else "field staff"
            alerts.append(
                {
                    "type": "overdue_assignment",
                    "severity": "warning",
                    "title": "Assignment overdue",
                    "message": f"POE pending for {booking.campaign.name} at {booking.media_unit.site.name} assigned to {assigned_to}.",
                    "related_id": booking.id,
                    "created_at": now,
                }
            )

        for poe_record in ProofOfExecution.objects.select_related("booking__campaign", "booking__media_unit__site").filter(
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS
        ):
            alerts.append(
                {
                    "type": "suspicious_poe",
                    "severity": "danger",
                    "title": "Suspicious POE",
                    "message": f"{poe_record.booking.campaign.name} at {poe_record.booking.media_unit.site.name} needs review.",
                    "related_id": poe_record.id,
                    "created_at": poe_record.updated_at,
                }
            )

        for poe_record in ProofOfExecution.objects.select_related("booking__campaign", "booking__media_unit__site").filter(
            verification_status=ProofOfExecution.VerificationStatus.REJECTED
        ):
            alerts.append(
                {
                    "type": "failed_verification",
                    "severity": "danger",
                    "title": "POE verification failed",
                    "message": f"{poe_record.booking.campaign.name} at {poe_record.booking.media_unit.site.name} failed verification.",
                    "related_id": poe_record.id,
                    "created_at": poe_record.updated_at,
                }
            )

        ending_cutoff = today + timedelta(days=3)
        for campaign in Campaign.objects.filter(end_date__gte=today, end_date__lte=ending_cutoff).exclude(
            status__in=[Campaign.Status.COMPLETED, Campaign.Status.CANCELLED]
        ):
            alerts.append(
                {
                    "type": "campaign_ending_soon",
                    "severity": "info",
                    "title": "Campaign ending soon",
                    "message": f"{campaign.name} ends on {campaign.end_date}.",
                    "related_id": campaign.id,
                    "created_at": now,
                }
            )

        return sorted(alerts, key=lambda item: item["created_at"], reverse=True)
