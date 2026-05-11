from io import BytesIO
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.bookings.models import Assignment, Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.poe.models import ProofOfExecution
from apps.poe.services import ProofOfExecutionService
from apps.users.models import User

from .models import Issue, IssueReportToken, IssueTask


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
        self.assertEqual(issue.priority, Issue.Priority.HIGH)
        self.assertIsNotNone(issue.first_response_due_at)
        self.assertIsNotNone(issue.resolution_due_at)
        self.assertEqual(issue.sla_status, Issue.SlaStatus.ON_TRACK)

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

    def test_critical_keywords_auto_raise_priority(self):
        self.client.force_authenticate(user=self.field_staff)

        response = self.client.post(
            "/api/v1/issues/",
            {
                "booking": self.booking.id,
                "reporter_type": Issue.ReporterType.FIELD_STAFF,
                "issue_type": Issue.IssueType.DAMAGE,
                "description": "Storm damage has left the frame collapsed and dangerous.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        issue = Issue.objects.get()
        self.assertEqual(issue.priority, Issue.Priority.CRITICAL)
        self.assertIn("Critical safety", issue.priority_reason)

    def test_sla_status_becomes_at_risk_when_first_response_due_passes(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.OTHER,
            description="Needs operational review.",
        )

        issue.first_response_due_at = timezone.now() - timedelta(minutes=1)
        issue.save()

        issue.refresh_from_db()
        self.assertEqual(issue.sla_status, Issue.SlaStatus.AT_RISK)

    def test_admin_can_generate_public_issue_report_token(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(f"/api/v1/bookings/{self.booking.id}/issue-report-token/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/report-issue/", response.data["public_url"])
        self.assertTrue(IssueReportToken.objects.filter(booking=self.booking).exists())

    def test_public_issue_report_context_is_limited(self):
        token = IssueReportToken.objects.create(
            booking=self.booking,
            expires_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(f"/api/v1/public/issue-report/{token.token}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["campaign_name"], self.campaign.name)
        self.assertEqual(response.data["site_name"], self.site.name)
        self.assertNotIn("client_email", response.data)

    def test_public_issue_report_creates_client_issue_with_auto_priority(self):
        token = IssueReportToken.objects.create(
            booking=self.booking,
            expires_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.post(
            f"/api/v1/public/issue-report/{token.token}/",
            {
                "issue_type": Issue.IssueType.DAMAGE,
                "description": "The creative is torn after storm conditions.",
                "contact": "client@example.com",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        issue = Issue.objects.get()
        self.assertEqual(issue.reporter_type, Issue.ReporterType.CLIENT)
        self.assertEqual(issue.contact, "client@example.com")
        self.assertEqual(issue.priority, Issue.Priority.CRITICAL)
        self.assertIsNotNone(issue.first_response_due_at)

    def test_expired_public_issue_report_token_is_rejected(self):
        token = IssueReportToken.objects.create(
            booking=self.booking,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        response = self.client.get(f"/api/v1/public/issue-report/{token.token}/")

        self.assertEqual(response.status_code, 410)

    def test_admin_can_assign_issue_task_to_field_staff(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.DAMAGE,
            description="Display skin is damaged.",
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f"/api/v1/issues/{issue.id}/assign-task/",
            {
                "assigned_to": self.other_staff.id,
                "due_at": (timezone.now() + timedelta(hours=6)).isoformat(),
                "notes": "Inspect and repair.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        task = IssueTask.objects.get()
        self.assertEqual(task.issue, issue)
        self.assertEqual(task.assigned_to, self.other_staff)
        self.assertEqual(task.assigned_by, self.admin)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.ACKNOWLEDGED)
        self.assertIsNotNone(issue.acknowledged_at)

    def test_admin_cannot_assign_issue_task_to_non_field_staff(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.OTHER,
            description="Needs follow up.",
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f"/api/v1/issues/{issue.id}/assign-task/",
            {
                "assigned_to": self.client_user.id,
                "due_at": (timezone.now() + timedelta(hours=6)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(IssueTask.objects.count(), 0)

    def test_duplicate_active_issue_task_is_rejected(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.OTHER,
            description="Needs follow up.",
        )
        IssueTask.objects.create(
            issue=issue,
            assigned_to=self.field_staff,
            assigned_by=self.admin,
            due_at=timezone.now() + timedelta(hours=4),
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            f"/api/v1/issues/{issue.id}/assign-task/",
            {
                "assigned_to": self.other_staff.id,
                "due_at": (timezone.now() + timedelta(hours=6)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(IssueTask.objects.count(), 1)

    def test_field_staff_can_view_and_update_own_issue_task(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.other_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.WRONG,
            description="Wrong creative installed.",
        )
        task = IssueTask.objects.create(
            issue=issue,
            assigned_to=self.field_staff,
            assigned_by=self.admin,
            due_at=timezone.now() + timedelta(hours=4),
        )
        self.client.force_authenticate(user=self.field_staff)

        task_response = self.client.get(f"/api/v1/issues/{issue.id}/task/")
        start_response = self.client.patch(
            f"/api/v1/tasks/{task.id}/",
            {"status": IssueTask.Status.IN_PROGRESS},
            format="json",
        )
        complete_response = self.client.patch(
            f"/api/v1/tasks/{task.id}/",
            {"status": IssueTask.Status.COMPLETED},
            format="json",
        )

        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(task_response.data["id"], task.id)
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(complete_response.status_code, 200)
        task.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(task.status, IssueTask.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(issue.status, Issue.Status.RESOLVED)
        self.assertIsNotNone(issue.resolved_at)

    def test_field_staff_cannot_update_other_staff_task(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.DAMAGE,
            description="Display skin is damaged.",
        )
        task = IssueTask.objects.create(
            issue=issue,
            assigned_to=self.other_staff,
            assigned_by=self.admin,
            due_at=timezone.now() + timedelta(hours=4),
        )
        self.client.force_authenticate(user=self.field_staff)

        response = self.client.patch(
            f"/api/v1/tasks/{task.id}/",
            {"status": IssueTask.Status.IN_PROGRESS},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_poe_created_after_issue_auto_resolves_open_issue(self):
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.MISSING,
            description="Creative is missing at site.",
        )

        ProofOfExecutionService().create(
            actor=self.field_staff,
            booking=self.booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            latitude="34.083700",
            longitude="74.797300",
        )

        issue.refresh_from_db()
        self.assertEqual(ProofOfExecution.objects.count(), 1)
        self.assertEqual(issue.status, Issue.Status.RESOLVED)

    def test_replacement_poe_after_new_issue_auto_resolves_open_issue(self):
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )
        issue = Issue.objects.create(
            booking=self.booking,
            assignment=self.assignment,
            reported_by=self.field_staff,
            reporter_type=Issue.ReporterType.FIELD_STAFF,
            issue_type=Issue.IssueType.DAMAGE,
            description="Creative was damaged after the original POE.",
        )

        replacement_poe = ProofOfExecutionService().create(
            actor=self.field_staff,
            booking=self.booking,
            executed_on=timezone.localdate(),
            captured_at=timezone.now(),
            latitude="34.083700",
            longitude="74.797300",
        )

        issue.refresh_from_db()
        self.assertEqual(ProofOfExecution.objects.filter(booking=self.booking).count(), 2)
        self.assertEqual(replacement_poe.booking, self.booking)
        self.assertEqual(issue.status, Issue.Status.RESOLVED)
