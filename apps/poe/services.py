from decimal import Decimal

from django.utils import timezone

from apps.notifications.services import trigger_poe_uploaded_notification
from apps.issues.services import resolve_open_issues_after_poe
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
