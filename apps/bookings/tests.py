from django.test import TestCase
from rest_framework.test import APIClient

from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.users.models import User

from .models import Assignment, Booking


class BookingAssignmentApiTests(TestCase):
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

    def test_booking_create_accepts_field_staff_user_id(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            "/api/v1/bookings/",
            {
                "campaign": self.campaign.id,
                "media_unit": self.unit.id,
                "start_date": "2026-05-01",
                "end_date": "2026-05-15",
                "booked_rate": "50000.00",
                "status": Booking.Status.CONFIRMED,
                "remarks": "Install before noon.",
                "field_staff_user_id": self.field_staff.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get()
        self.assertTrue(booking.assignments.filter(user=self.field_staff, status=Assignment.Status.PENDING).exists())
        self.assertEqual(response.data["assigned_user"]["id"], self.field_staff.id)

    def test_booking_patch_can_unassign_without_deleting_history(self):
        booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date="2026-05-01",
            end_date="2026-05-15",
            booked_rate="50000.00",
            status=Booking.Status.CONFIRMED,
        )
        Assignment.objects.create(booking=booking, user=self.field_staff, assigned_by=self.admin)
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            f"/api/v1/bookings/{booking.id}/",
            {"field_staff_user_id": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["assigned_user"])
        assignment = booking.assignments.get(user=self.field_staff)
        self.assertEqual(assignment.status, Assignment.Status.CANCELLED)
