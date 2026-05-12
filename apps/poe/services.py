from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.notifications.services import trigger_poe_uploaded_notification
from apps.issues.services import resolve_open_issues_after_poe
from apps.inventory.models import MediaSite
from core.services import BaseService

from .exceptions import DuplicateProofOfExecutionError
from .models import ProofOfExecution
from .repositories import (
    ProofOfExecutionMediaRepository,
    ProofOfExecutionRepository,
    ProofOfExecutionVerificationLogRepository,
)
from .verification import DEFAULT_DISTANCE_THRESHOLD_METERS, ProofOfExecutionVerificationEngine
from .verification import haversine_distance_meters


class ProofOfExecutionService(BaseService):
    repository_class = ProofOfExecutionRepository
    REPLACEMENT_ALLOWED_STATUSES = {
        ProofOfExecution.VerificationStatus.SUSPICIOUS,
        ProofOfExecution.VerificationStatus.REJECTED,
    }

    def _booking_has_new_open_issue(self, booking, existing_poe: ProofOfExecution) -> bool:
        from apps.issues.models import Issue

        return (
            Issue.objects.filter(booking=booking, created_at__gt=existing_poe.created_at)
            .exclude(status=Issue.Status.RESOLVED)
            .exists()
        )

    def _should_block_duplicate(self, booking, existing_poe: ProofOfExecution) -> bool:
        if existing_poe.verification_status in self.REPLACEMENT_ALLOWED_STATUSES:
            return False
        return not self._booking_has_new_open_issue(booking, existing_poe)

    def create(self, actor=None, **validated_data):
        booking = validated_data.get("booking")
        if booking:
            existing_poe = ProofOfExecution.objects.filter(booking=booking).order_by("-created_at", "-id").first()
            if existing_poe and self._should_block_duplicate(booking, existing_poe):
                raise DuplicateProofOfExecutionError(existing_poe)

        if "captured_at" not in validated_data:
            validated_data["captured_at"] = timezone.now()
        if "review_due_at" not in validated_data or not validated_data.get("review_due_at"):
            captured_at = validated_data["captured_at"]
            validated_data["review_due_at"] = captured_at + timedelta(hours=getattr(settings, "POE_REVIEW_SLA_HOURS", 24))
        validated_data["review_sla_status"] = resolve_review_sla_status_from_values(
            reviewed_at=validated_data.get("reviewed_at"),
            review_due_at=validated_data.get("review_due_at"),
        )
        poe_record = super().create(actor=actor, **validated_data)
        self.capture_first_poe_location(poe_record)
        if booking:
            resolve_open_issues_after_poe(booking, poe_created_at=poe_record.created_at)
        return poe_record

    def mark_verified(self, instance):
        return self.update(
            instance,
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )

    def approve_record(self, instance, actor=None, comment: str = ""):
        comment = (comment or "").strip()
        updated = self.update(
            instance,
            checked_by=actor if actor else instance.checked_by,
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
            verification_score=Decimal("100.00"),
            verification_notes="Manually approved by operations review.",
            review_comment=comment,
            reviewed_at=timezone.now(),
            review_sla_status=ProofOfExecution.ReviewSlaStatus.REVIEWED,
        )
        self.lock_site_location_from_verified_poe(updated, actor=actor)
        return updated

    def reject_record(self, instance, actor=None, reason: str = "", comment: str = ""):
        reason = (reason or "").strip() or "Manually rejected by operations review."
        review_comment = (comment or reason).strip()
        updated = self.update(
            instance,
            checked_by=actor if actor else instance.checked_by,
            verification_status=ProofOfExecution.VerificationStatus.REJECTED,
            verification_notes=reason,
            review_comment=review_comment,
            reviewed_at=timezone.now(),
            review_sla_status=ProofOfExecution.ReviewSlaStatus.REVIEWED,
        )
        self.mark_site_location_suspicious(updated)
        try:
            from apps.notifications.services import trigger_suspicious_poe_notification

            trigger_suspicious_poe_notification(updated, actor=actor)
        except Exception:
            pass
        return updated

    def verify_record(self, instance, actor=None, distance_threshold_meters=DEFAULT_DISTANCE_THRESHOLD_METERS):
        engine = ProofOfExecutionVerificationEngine()
        outcome = engine.verify(instance, distance_threshold_meters=distance_threshold_meters)
        status_before = instance.verification_status

        updated_instance = self.update(
            instance,
            checked_by=actor if actor else instance.checked_by,
            verification_status=outcome.status,
            verification_score=outcome.score,
            verification_notes=outcome.verification_notes,
            reviewed_at=timezone.now(),
            review_sla_status=ProofOfExecution.ReviewSlaStatus.REVIEWED,
        )
        if outcome.status == ProofOfExecution.VerificationStatus.VERIFIED:
            self.lock_site_location_from_verified_poe(updated_instance, actor=actor)
        elif outcome.status in {
            ProofOfExecution.VerificationStatus.SUSPICIOUS,
            ProofOfExecution.VerificationStatus.REJECTED,
        }:
            self.mark_site_location_suspicious(updated_instance)
            try:
                from apps.notifications.services import trigger_suspicious_poe_notification

                trigger_suspicious_poe_notification(updated_instance, actor=actor)
            except Exception:
                pass

        ProofOfExecutionVerificationLogService().create(
            actor=actor,
            poe_record=updated_instance,
            verified_by=actor,
            status_before=status_before,
            status_after=outcome.status,
            verification_score=outcome.score,
            distance_meters=outcome.distance_meters,
            threshold_meters=Decimal(distance_threshold_meters),
            notes=outcome.verification_notes,
            result_payload=outcome.as_payload(),
        )

        return {
            "poe_record": updated_instance.id,
            "verification_status": outcome.status,
            "verification_score": outcome.score,
            "verification_notes": outcome.verification_notes,
            "suspicious": outcome.suspicious,
            "distance_meters": outcome.distance_meters,
            "threshold_meters": outcome.threshold_meters,
            "image_comparison": outcome.image_comparison,
            "content_validation": outcome.content_validation,
        }

    def capture_first_poe_location(self, poe_record: ProofOfExecution):
        site = self._get_site(poe_record)
        if not site or not self._poe_has_coordinates(poe_record) or self._site_location_locked(site):
            return

        if site.latitude is None or site.longitude is None:
            site.latitude = poe_record.latitude
            site.longitude = poe_record.longitude
            site.location_status = MediaSite.LocationStatus.PROVISIONAL
            site.location_source = MediaSite.LocationSource.FIRST_VERIFIED_POE
            site.save(
                update_fields=[
                    "latitude",
                    "longitude",
                    "location_status",
                    "location_source",
                    "updated_at",
                ]
            )

    def lock_site_location_from_verified_poe(self, poe_record: ProofOfExecution, *, actor=None):
        site = self._get_site(poe_record)
        if not site or not self._poe_has_coordinates(poe_record) or self._site_location_locked(site):
            return

        site.latitude = poe_record.latitude
        site.longitude = poe_record.longitude
        site.location_status = MediaSite.LocationStatus.VERIFIED
        site.location_source = MediaSite.LocationSource.FIRST_VERIFIED_POE
        site.location_verified_at = timezone.now()
        site.location_verified_by = actor
        site.save(
            update_fields=[
                "latitude",
                "longitude",
                "location_status",
                "location_source",
                "location_verified_at",
                "location_verified_by",
                "updated_at",
            ]
        )

    def mark_site_location_suspicious(self, poe_record: ProofOfExecution):
        site = self._get_site(poe_record)
        if not site or self._site_location_locked(site):
            return
        site.location_status = MediaSite.LocationStatus.SUSPICIOUS
        site.save(update_fields=["location_status", "updated_at"])

    def _get_site(self, poe_record: ProofOfExecution):
        return getattr(getattr(getattr(poe_record, "booking", None), "media_unit", None), "site", None)

    def _poe_has_coordinates(self, poe_record: ProofOfExecution) -> bool:
        return poe_record.latitude is not None and poe_record.longitude is not None

    def _site_location_locked(self, site: MediaSite) -> bool:
        return (
            site.location_status == MediaSite.LocationStatus.VERIFIED
            and site.latitude is not None
            and site.longitude is not None
        )


def build_location_confidence(poe_record: ProofOfExecution, *, threshold_meters=DEFAULT_DISTANCE_THRESHOLD_METERS) -> dict:
    site = getattr(getattr(getattr(poe_record, "booking", None), "media_unit", None), "site", None)
    threshold = Decimal(threshold_meters)
    distance = None
    within_radius = None
    status = "missing_gps"

    poe_has_coordinates = poe_record.latitude is not None and poe_record.longitude is not None
    site_has_coordinates = bool(site and site.latitude is not None and site.longitude is not None)

    if poe_has_coordinates and site_has_coordinates:
        distance = haversine_distance_meters(
            poe_record.latitude,
            poe_record.longitude,
            site.latitude,
            site.longitude,
        )
        within_radius = distance <= threshold
        status = "within_radius" if within_radius else "suspicious"
    elif site and site.location_status == MediaSite.LocationStatus.UNVERIFIED:
        status = "site_unverified"
    elif not poe_has_coordinates:
        status = "poe_gps_missing"
    elif not site_has_coordinates:
        status = "site_gps_missing"

    latest_log = poe_record.verification_logs.order_by("-created_at").first() if poe_record.pk else None
    if latest_log and latest_log.distance_meters is not None:
        distance = latest_log.distance_meters
        threshold = latest_log.threshold_meters
        within_radius = distance <= threshold
        status = "within_radius" if within_radius else "suspicious"

    return {
        "captured_latitude": poe_record.latitude,
        "captured_longitude": poe_record.longitude,
        "distance_meters": distance,
        "threshold_meters": threshold,
        "within_allowed_radius": within_radius,
        "location_confidence_status": status,
        "site_location_status": getattr(site, "location_status", ""),
    }


def resolve_review_sla_status_from_values(*, reviewed_at=None, review_due_at=None, now=None) -> str:
    now = now or timezone.now()
    if reviewed_at:
        return ProofOfExecution.ReviewSlaStatus.REVIEWED
    if review_due_at and now > review_due_at:
        return ProofOfExecution.ReviewSlaStatus.OVERDUE
    return ProofOfExecution.ReviewSlaStatus.ON_TRACK


def resolve_review_sla_status(poe_record: ProofOfExecution, *, now=None) -> str:
    return resolve_review_sla_status_from_values(
        reviewed_at=poe_record.reviewed_at,
        review_due_at=poe_record.review_due_at,
        now=now,
    )


class ProofOfExecutionMediaService(BaseService):
    repository_class = ProofOfExecutionMediaRepository

    def create(self, actor=None, **validated_data):
        if actor and "captured_by" not in validated_data:
            validated_data["captured_by"] = actor
        if "captured_at" not in validated_data:
            validated_data["captured_at"] = timezone.now()
        media = super().create(actor=actor, **validated_data)
        trigger_poe_uploaded_notification(media, actor=actor)
        return media


class ProofOfExecutionVerificationLogService(BaseService):
    repository_class = ProofOfExecutionVerificationLogRepository
