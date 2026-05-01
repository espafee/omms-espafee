from __future__ import annotations

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings.models import Assignment, Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia
from apps.users.models import User


class MobileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@example.com",
            username="admin",
            password="secret",
            role=User.Role.ADMIN,
        )
        self.field_staff = User.objects.create_user(
            email="field@example.com",
            username="field",
            password="secret",
            role=User.Role.FIELD_STAFF,
        )
        self.other_staff = User.objects.create_user(
            email="other@example.com",
            username="other",
            password="secret",
            role=User.Role.FIELD_STAFF,
        )
        self.client_user = User.objects.create_user(
            email="client@example.com",
            username="client",
            password="secret",
            role=User.Role.CLIENT,
        )
        self.site = MediaSite.objects.create(
            name="Residency Road",
            code="SITE-1",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Residency Road",
            city="Jammu",
            state="Jammu and Kashmir",
            latitude="34.083700",
            longitude="74.797300",
            owner=self.field_staff,
        )
        self.other_site = MediaSite.objects.create(
            name="Airport Road",
            code="SITE-2",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Airport Road",
            city="Jammu",
            state="Jammu and Kashmir",
            latitude="34.090000",
            longitude="74.800000",
            owner=self.other_staff,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="Hoarding A",
            face_count=1,
            width="20.00",
            height="10.00",
            monthly_rate="50000.00",
        )
        self.other_unit = MediaUnit.objects.create(
            site=self.other_site,
            unit_code="Hoarding B",
            face_count=1,
            width="20.00",
            height="10.00",
            monthly_rate="50000.00",
        )
        self.campaign = Campaign.objects.create(
            name="Jio Summer Campaign",
            code="CMP-1",
            client=self.client_user,
            start_date="2026-05-01",
            end_date="2026-05-15",
            budget="100000.00",
            status=Campaign.Status.ACTIVE,
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date="2026-05-01",
            end_date="2026-05-15",
            booked_rate="50000.00",
            status=Booking.Status.CONFIRMED,
        )
        self.other_booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.other_unit,
            start_date="2026-05-01",
            end_date="2026-05-15",
            booked_rate="50000.00",
            status=Booking.Status.CONFIRMED,
        )
        Assignment.objects.create(booking=self.booking, user=self.field_staff, assigned_by=self.admin)

    def _authenticate(self, user):
        self.client.force_authenticate(user=user)

    def _build_image(self):
        buffer = BytesIO()
        image = Image.new("RGB", (80, 60), color="green")
        image.save(buffer, format="JPEG")
        return SimpleUploadedFile("poe.jpg", buffer.getvalue(), content_type="image/jpeg")

    def test_assigned_work_returns_only_assigned_bookings_for_field_staff(self):
        self._authenticate(self.field_staff)

        response = self.client.get("/api/v1/mobile/assigned-work/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(item["booking_id"], self.booking.id)
        self.assertEqual(item["campaign_name"], "Jio Summer Campaign")
        self.assertEqual(item["site_name"], "Residency Road")
        self.assertEqual(item["unit_name"], "Hoarding A")
        self.assertEqual(item["location"], "Jammu")
        self.assertEqual(item["poe_status"], "pending")

    def test_admin_can_see_all_mobile_work(self):
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/assigned-work/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_mobile_poe_submit_creates_record_media_and_verification(self):
        self._authenticate(self.field_staff)
        captured_at = timezone.make_aware(timezone.datetime(2026, 5, 5, 10, 0, 0))

        response = self.client.post(
            "/api/v1/mobile/poe/submit/",
            {
                "booking_id": self.booking.id,
                "image": self._build_image(),
                "latitude": "34.083710",
                "longitude": "74.797310",
                "captured_at": captured_at.isoformat(),
                "notes": "Installed and photographed.",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["detail"], "POE submitted successfully.")
        self.assertEqual(response.data["status"], ProofOfExecution.VerificationStatus.VERIFIED)
        self.assertIsNotNone(response.data["distance_meters"])
        self.assertEqual(ProofOfExecution.objects.count(), 1)
        self.assertEqual(ProofOfExecutionMedia.objects.count(), 1)
        poe = ProofOfExecution.objects.get()
        self.assertEqual(poe.booking, self.booking)
        self.assertEqual(poe.notes, "Installed and photographed.")

    def test_mobile_poe_submit_rejects_unassigned_booking(self):
        self._authenticate(self.field_staff)

        response = self.client.post(
            "/api/v1/mobile/poe/submit/",
            {
                "booking_id": self.other_booking.id,
                "image": self._build_image(),
                "latitude": "34.083710",
                "longitude": "74.797310",
                "captured_at": timezone.now().isoformat(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ProofOfExecution.objects.count(), 0)

    def test_mobile_admin_overview_allows_admin_and_returns_expected_keys(self):
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data.keys()),
            {
                "active_campaigns",
                "poe_pending",
                "poe_completed_today",
                "suspicious_poe",
                "bookings_starting_today",
                "bookings_ending_today",
            },
        )

    def test_mobile_admin_overview_rejects_field_staff(self):
        self._authenticate(self.field_staff)

        response = self.client.get("/api/v1/mobile/admin/overview/")

        self.assertEqual(response.status_code, 403)

    def test_mobile_admin_running_campaigns_returns_expected_shape(self):
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/running-campaigns/")

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
        item = response.data[0]
        self.assertIn("campaign_id", item)
        self.assertIn("campaign_name", item)
        self.assertIn("client_name", item)
        self.assertIn("total_units", item)
        self.assertIn("poe_progress_percent", item)

    def test_mobile_admin_poe_tracker_status_filter(self):
        suspicious_poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS,
        )
        ProofOfExecution.objects.create(
            booking=self.other_booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/poe-tracker/?status=suspicious")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["poe_id"], suspicious_poe.id)
        self.assertEqual(response.data[0]["status"], ProofOfExecution.VerificationStatus.SUSPICIOUS)
