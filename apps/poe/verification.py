from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import atan2, cos, radians, sin, sqrt

from django.utils import timezone


DEFAULT_DISTANCE_THRESHOLD_METERS = Decimal("250.00")
REJECT_DISTANCE_MULTIPLIER = Decimal("2.00")


def quantize_score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def clamp_score(value: Decimal) -> Decimal:
    return max(Decimal("0.00"), min(Decimal("100.00"), quantize_score(value)))


def haversine_distance_meters(latitude_one, longitude_one, latitude_two, longitude_two) -> Decimal:
    earth_radius = 6371000

    lat_one = radians(float(latitude_one))
    lon_one = radians(float(longitude_one))
    lat_two = radians(float(latitude_two))
    lon_two = radians(float(longitude_two))

    delta_lat = lat_two - lat_one
    delta_lon = lon_two - lon_one

    a = sin(delta_lat / 2) ** 2 + cos(lat_one) * cos(lat_two) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return quantize_score(Decimal(str(earth_radius * c)))


@dataclass
class VerificationOutcome:
    status: str
    score: Decimal
    verification_notes: str
    distance_meters: Decimal | None
    threshold_meters: Decimal
    suspicious: bool
    image_comparison: dict
    content_validation: dict

    def as_payload(self):
        return {
            "status": self.status,
            "score": str(self.score),
            "verification_notes": self.verification_notes,
            "distance_meters": str(self.distance_meters) if self.distance_meters is not None else None,
            "threshold_meters": str(self.threshold_meters),
            "suspicious": self.suspicious,
            "image_comparison": self.image_comparison,
            "content_validation": self.content_validation,
        }


class ProofOfExecutionVerificationEngine:
    def compare_uploaded_image_to_inventory(self, poe_record):
        media_count = poe_record.media_items.count()
        return {
            "implemented": False,
            "score_delta": 0,
            "summary": "AI image comparison placeholder. Hook a CV model here later.",
            "media_items_seen": media_count,
        }

    def validate_visible_content(self, poe_record):
        return {
            "implemented": False,
            "score_delta": 0,
            "summary": "Content validation placeholder. Hook OCR / branding checks here later.",
        }

    def verify(self, poe_record, distance_threshold_meters=DEFAULT_DISTANCE_THRESHOLD_METERS):
        threshold = Decimal(distance_threshold_meters)
        score = Decimal("100.00")
        notes = []
        suspicious = False
        distance_meters = None

        site = poe_record.booking.media_unit.site
        site_has_coordinates = site.latitude is not None and site.longitude is not None
        poe_has_coordinates = poe_record.latitude is not None and poe_record.longitude is not None

        if site_has_coordinates and poe_has_coordinates:
            distance_meters = haversine_distance_meters(
                poe_record.latitude,
                poe_record.longitude,
                site.latitude,
                site.longitude,
            )

            if distance_meters > threshold * REJECT_DISTANCE_MULTIPLIER:
                score -= Decimal("70.00")
                suspicious = True
                notes.append(
                    f"Uploaded GPS is {distance_meters} meters away from the booked site, far beyond the threshold."
                )
            elif distance_meters > threshold:
                score -= Decimal("35.00")
                suspicious = True
                notes.append(
                    f"Uploaded GPS is {distance_meters} meters away from the booked site, above the threshold."
                )
            else:
                notes.append(f"GPS check passed. Uploaded location is {distance_meters} meters from the booked site.")
        else:
            score -= Decimal("25.00")
            if not site_has_coordinates:
                notes.append("The booked site does not have GPS coordinates configured.")
            if not poe_has_coordinates:
                notes.append("The uploaded POE record did not include GPS coordinates.")

        if poe_record.captured_at:
            booking = poe_record.booking
            capture_date = timezone.localtime(poe_record.captured_at).date()
            if capture_date < booking.start_date or capture_date > booking.end_date:
                score -= Decimal("15.00")
                suspicious = True
                notes.append("Capture timestamp is outside the booked campaign window.")
            else:
                notes.append("Capture timestamp falls within the booked campaign window.")
        else:
            score -= Decimal("10.00")
            notes.append("Capture timestamp is missing.")

        if not poe_record.media_items.exists():
            score -= Decimal("20.00")
            suspicious = True
            notes.append("No proof media is attached to this POE record.")
        else:
            notes.append(f"{poe_record.media_items.count()} proof media item(s) attached.")

        image_comparison = self.compare_uploaded_image_to_inventory(poe_record)
        content_validation = self.validate_visible_content(poe_record)

        score += Decimal(str(image_comparison.get("score_delta", 0)))
        score += Decimal(str(content_validation.get("score_delta", 0)))
        score = clamp_score(score)

        if score >= Decimal("85.00") and not suspicious:
            status = poe_record.VerificationStatus.VERIFIED
        elif suspicious and distance_meters is not None and distance_meters > threshold * REJECT_DISTANCE_MULTIPLIER:
            status = poe_record.VerificationStatus.REJECTED
        elif suspicious:
            status = poe_record.VerificationStatus.SUSPICIOUS
        else:
            status = poe_record.VerificationStatus.PENDING

        return VerificationOutcome(
            status=status,
            score=score,
            verification_notes=" ".join(notes),
            distance_meters=distance_meters,
            threshold_meters=quantize_score(threshold),
            suspicious=suspicious,
            image_comparison=image_comparison,
            content_validation=content_validation,
        )
