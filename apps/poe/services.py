from decimal import Decimal

from django.utils import timezone

from core.services import BaseService

from .models import ProofOfExecution
from .repositories import (
    ProofOfExecutionMediaRepository,
    ProofOfExecutionRepository,
    ProofOfExecutionVerificationLogRepository,
)
from .verification import DEFAULT_DISTANCE_THRESHOLD_METERS, ProofOfExecutionVerificationEngine


class ProofOfExecutionService(BaseService):
    repository_class = ProofOfExecutionRepository

    def create(self, actor=None, **validated_data):
        if "captured_at" not in validated_data:
            validated_data["captured_at"] = timezone.now()
        return super().create(actor=actor, **validated_data)

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
        return super().create(actor=actor, **validated_data)


class ProofOfExecutionVerificationLogService(BaseService):
    repository_class = ProofOfExecutionVerificationLogRepository
