from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia, ProofOfExecutionVerificationLog

User = get_user_model()


class PoeVerificationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "TestPass123!"

        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.operations = self._create_user("ops@example.com", "ops_user", User.Role.OPERATIONS)
        self.client_user = self._create_user("client@example.com", "client_user", User.Role.CLIENT)

        self.site = MediaSite.objects.create(
            name="Verification Billboard",
            code="SITE-VERIFY-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Western Express Highway",
            city="Mumbai",
            state="Maharashtra",
            latitude=Decimal("19.076000"),
            longitude=Decimal("72.877700"),
            owner=self.operations,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-VERIFY-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.RESERVED,
            is_illuminated=True,
            monthly_rate=Decimal("85000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="Verification Campaign",
            code="CMP-VERIFY-001",
            client=self.client_user,
            account_manager=self.admin,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Verification workflow",
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            booked_rate=Decimal("90000.00"),
            status=Booking.Status.CONFIRMED,
        )

    def _create_user(self, email, username, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
        )

    def _create_poe(self, latitude, longitude):
        poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=timezone.now(),
            latitude=Decimal(latitude),
            longitude=Decimal(longitude),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )
        ProofOfExecutionMedia.objects.create(
            poe_record=poe,
            media_url="https://example.com/proof.jpg",
            media_type="image",
            captured_by=self.operations,
        )
        return poe

    def test_verify_endpoint_marks_record_verified_when_location_matches(self):
        poe = self._create_poe("19.076500", "72.878000")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(reverse("poe-verify"), {"poe_record": poe.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["verification_status"], ProofOfExecution.VerificationStatus.VERIFIED)
        self.assertIn("GPS check passed", response.data["verification_notes"])
        poe.refresh_from_db()
        self.assertEqual(poe.verification_status, ProofOfExecution.VerificationStatus.VERIFIED)
        self.assertEqual(ProofOfExecutionVerificationLog.objects.filter(poe_record=poe).count(), 1)

    def test_verify_endpoint_marks_record_suspicious_when_distance_exceeds_threshold(self):
        poe = self._create_poe("19.078700", "72.877700")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(reverse("poe-verify"), {"poe_record": poe.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["verification_status"], ProofOfExecution.VerificationStatus.SUSPICIOUS)
        self.assertTrue(response.data["suspicious"])
        self.assertIsNotNone(response.data["distance_meters"])
        poe.refresh_from_db()
        self.assertEqual(poe.verification_status, ProofOfExecution.VerificationStatus.SUSPICIOUS)

    def test_verify_endpoint_rejects_record_when_far_beyond_threshold(self):
        poe = self._create_poe("19.090000", "72.910000")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(reverse("poe-verify"), {"poe_record": poe.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["verification_status"], ProofOfExecution.VerificationStatus.REJECTED)
        poe.refresh_from_db()
        self.assertEqual(poe.verification_status, ProofOfExecution.VerificationStatus.REJECTED)

    def test_client_cannot_verify_poe(self):
        poe = self._create_poe("19.076500", "72.878000")
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(reverse("poe-verify"), {"poe_record": poe.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_poe_create_endpoint_rejects_duplicate_booking_submission(self):
        existing_poe = self._create_poe("19.076500", "72.878000")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("poe-list"),
            {
                "booking": self.booking.id,
                "executed_on": str(date.today()),
                "captured_at": timezone.now().isoformat(),
                "latitude": "19.076500",
                "longitude": "72.878000",
                "notes": "Duplicate attempt.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "POE already submitted for this booking.")
        self.assertEqual(response.data["poe_id"], existing_poe.id)
        self.assertEqual(response.data["status"], ProofOfExecution.VerificationStatus.PENDING)

    def test_poe_create_endpoint_allows_replacement_after_rejected_poe(self):
        existing_poe = self._create_poe("19.090000", "72.910000")
        existing_poe.verification_status = ProofOfExecution.VerificationStatus.REJECTED
        existing_poe.save(update_fields=["verification_status", "updated_at"])
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("poe-list"),
            {
                "booking": self.booking.id,
                "executed_on": str(date.today()),
                "captured_at": timezone.now().isoformat(),
                "latitude": "19.076500",
                "longitude": "72.878000",
                "notes": "Replacement after rejected POE.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProofOfExecution.objects.filter(booking=self.booking).count(), 2)
        self.assertNotEqual(response.data["id"], existing_poe.id)

    def test_verify_response_exposes_future_ai_placeholder_structure(self):
        poe = self._create_poe("19.076500", "72.878000")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(reverse("poe-verify"), {"poe_record": poe.id}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("image_comparison", response.data)
        self.assertIn("content_validation", response.data)
        self.assertFalse(response.data["image_comparison"]["implemented"])
        self.assertFalse(response.data["content_validation"]["implemented"])
