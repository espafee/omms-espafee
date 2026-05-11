from decimal import Decimal

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
        )
        if outcome.status == ProofOfExecution.VerificationStatus.VERIFIED:
            self.lock_site_location_from_verified_poe(updated_instance, actor=actor)
        elif outcome.status in {
            ProofOfExecution.VerificationStatus.SUSPICIOUS,
            ProofOfExecution.VerificationStatus.REJECTED,
        }:
            self.mark_site_location_suspicious(updated_instance)

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
