from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings.models import Assignment, Booking
from apps.billing.models import Invoice
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.issues.models import Issue
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

    def test_mobile_poe_submit_rejects_duplicate_for_field_staff(self):
        existing_poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )
        self._authenticate(self.field_staff)

        response = self.client.post(
            "/api/v1/mobile/poe/submit/",
            {
                "booking_id": self.booking.id,
                "image": self._build_image(),
                "latitude": "34.083710",
                "longitude": "74.797310",
                "captured_at": timezone.now().isoformat(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "POE already submitted for this booking.")
        self.assertEqual(response.data["poe_id"], existing_poe.id)
        self.assertEqual(response.data["status"], ProofOfExecution.VerificationStatus.VERIFIED)
        self.assertEqual(ProofOfExecution.objects.count(), 1)

    def test_mobile_poe_submit_rejects_duplicate_for_admin(self):
        existing_poe = ProofOfExecution.objects.create(
            booking=self.other_booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )
        self._authenticate(self.admin)

        response = self.client.post(
            "/api/v1/mobile/poe/submit/",
            {
                "booking_id": self.other_booking.id,
                "image": self._build_image(),
                "latitude": "34.090000",
                "longitude": "74.800000",
                "captured_at": timezone.now().isoformat(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["poe_id"], existing_poe.id)
        self.assertEqual(response.data["status"], ProofOfExecution.VerificationStatus.PENDING)
        self.assertEqual(ProofOfExecution.objects.count(), 1)

    def test_mobile_admin_overview_allows_admin_and_returns_expected_keys(self):
        Invoice.objects.create(
            campaign=self.campaign,
            invoice_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=10),
            total_amount=Decimal("5000.00"),
            grand_total=Decimal("5000.00"),
            status=Invoice.Status.ISSUED,
        )
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data.keys()),
            {
                "active_campaigns",
                "campaigns_at_risk",
                "campaigns_ending_soon",
                "critical_campaigns",
                "poe_pending",
                "poe_completed_today",
                "suspicious_poe",
                "poe_sla_warnings",
                "poe_sla_breaches",
                "overdue_invoices",
                "overdue_invoice_value",
                "collection_efficiency",
                "bookings_starting_today",
                "bookings_ending_today",
            },
        )
        self.assertEqual(response.data["overdue_invoices"], 1)
        self.assertEqual(response.data["overdue_invoice_value"], "5000.00")
        self.assertIn("campaigns_at_risk", response.data)
        self.assertIn("campaigns_ending_soon", response.data)
        self.assertIn("critical_campaigns", response.data)

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

    def test_mobile_admin_search_returns_campaign_and_site_lookup(self):
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/search/?q=Jio&modules=campaigns,sites,units")

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertIn("campaigns", {item["module"] for item in response.data["results"]})

    def test_mobile_admin_search_rejects_field_staff(self):
        self._authenticate(self.field_staff)

        response = self.client.get("/api/v1/mobile/admin/search/?q=Jio")

        self.assertEqual(response.status_code, 403)

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

    def test_mobile_admin_alerts_include_overdue_assignment(self):
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/alerts/")

        self.assertEqual(response.status_code, 200)
        overdue_alerts = [item for item in response.data if item["type"] == "overdue_assignment"]
        self.assertEqual(len(overdue_alerts), 1)
        self.assertEqual(overdue_alerts[0]["related_id"], self.booking.id)
        self.assertEqual(overdue_alerts[0]["severity"], "warning")
        self.assertIn("assigned to", overdue_alerts[0]["message"])

    def test_mobile_admin_daily_activity_includes_overdue_assignment(self):
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/daily-activity/")

        self.assertEqual(response.status_code, 200)
        overdue_items = [item for item in response.data["overdue_items"] if item["booking_id"] == self.booking.id]
        self.assertEqual(len(overdue_items), 1)
        self.assertEqual(overdue_items[0]["status"], "overdue")
        self.assertEqual(overdue_items[0]["assigned_to"], self.field_staff.email)
        self.assertEqual(overdue_items[0]["due_date"], self.booking.start_date)

    def test_mobile_admin_alerts_include_reported_issue(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.booking.assignments.first(),
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.DAMAGE,
            description="Display frame is damaged.",
            priority=Issue.Priority.CRITICAL,
        )
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/alerts/")

        self.assertEqual(response.status_code, 200)
        issue_alerts = [item for item in response.data if item["type"] == "reported_issue"]
        self.assertEqual(len(issue_alerts), 1)
        self.assertEqual(issue_alerts[0]["related_id"], issue.id)
        self.assertEqual(issue_alerts[0]["severity"], "danger")

    def test_mobile_admin_issues_returns_issue_list(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.booking.assignments.first(),
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.WRONG,
            description="Wrong flex installed.",
            priority=Issue.Priority.HIGH,
        )
        self._authenticate(self.admin)

        response = self.client.get("/api/v1/mobile/admin/issues/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["issue_id"], issue.id)
        self.assertEqual(response.data[0]["booking_id"], self.booking.id)
        self.assertEqual(response.data[0]["issue_type"], Issue.IssueType.WRONG)
