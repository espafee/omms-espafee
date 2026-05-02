from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings.models import Assignment, Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.users.models import User

from .models import Issue


class IssueApiTests(TestCase):
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
            city="Jammu",
            state="Jammu and Kashmir",
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="Hoarding A",
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
        self.assignment = Assignment.objects.create(booking=self.booking, user=self.field_staff, assigned_by=self.admin)

    def _image(self):
        buffer = BytesIO()
        Image.new("RGB", (64, 48), color="red").save(buffer, format="JPEG")
        return SimpleUploadedFile("issue.jpg", buffer.getvalue(), content_type="image/jpeg")

    def test_field_staff_can_create_issue_for_assigned_booking(self):
        self.client.force_authenticate(user=self.field_staff)

        response = self.client.post(
            "/api/v1/issues/",
            {
                "booking": self.booking.id,
                "reporter_type": Issue.ReporterType.FIELD_STAFF,
                "issue_type": Issue.IssueType.DAMAGE,
                "description": "Creative is damaged on arrival.",
                "priority": Issue.Priority.HIGH,
                "latitude": "34.083700",
                "longitude": "74.797300",
                "image": self._image(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        issue = Issue.objects.get()
        self.assertEqual(issue.reported_by, self.field_staff)
        self.assertEqual(issue.assignment, self.assignment)
        self.assertEqual(issue.status, Issue.Status.REPORTED)

    def test_field_staff_cannot_create_issue_for_unassigned_booking(self):
        self.client.force_authenticate(user=self.other_staff)

        response = self.client.post(
            "/api/v1/issues/",
            {
                "booking": self.booking.id,
                "reporter_type": Issue.ReporterType.FIELD_STAFF,
                "issue_type": Issue.IssueType.MISSING,
                "description": "Not assigned to me.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Issue.objects.count(), 0)

    def test_admin_can_list_and_update_issue(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.WRONG,
            description="Wrong creative installed.",
            priority=Issue.Priority.MEDIUM,
        )
        self.client.force_authenticate(user=self.admin)

        list_response = self.client.get("/api/v1/issues/")
        patch_response = self.client.patch(
            f"/api/v1/issues/{issue.id}/",
            {"status": Issue.Status.RESOLVED, "priority": Issue.Priority.HIGH},
            format="json",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(patch_response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.RESOLVED)
        self.assertIsNotNone(issue.resolved_at)
