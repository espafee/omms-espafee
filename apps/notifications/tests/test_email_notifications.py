from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.bookings.services import BookingService
from apps.campaigns.models import Campaign
from apps.notifications.models import EmailNotificationLog, Notification, NotificationPreference
from apps.notifications.services import NotificationService
from apps.poe.models import ProofOfExecution
from apps.poe.services import ProofOfExecutionMediaService
from apps.users.models import User
from apps.inventory.models import MediaSite, MediaUnit


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="no-reply@omms.test",
    FRONTEND_PUBLIC_BASE_URL="https://omms.vercel.app",
    NOTIFICATION_COMPANY_NAME="OMMS Control",
)
class EmailNotificationTests(TestCase):
    def _build_uploaded_image(self, name="proof.jpg"):
        buffer = BytesIO()
        image = Image.new("RGB", (20, 20), color="red")
        image.save(buffer, format="JPEG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", username="admin", password="x", role=User.Role.ADMIN)
        self.sales = User.objects.create_user(email="sales@example.com", username="sales", password="x", role=User.Role.SALES)
        self.operations = User.objects.create_user(email="ops@example.com", username="ops", password="x", role=User.Role.OPERATIONS)
        self.client_user = User.objects.create_user(
            email="client@example.com",
            username="client",
            password="x",
            role=User.Role.CLIENT,
            organization_name="Acme Outdoor",
        )
        self.site = MediaSite.objects.create(
            name="SIDCO Chowk",
            code="SITE-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Main Road",
            city="Jammu",
            state="Jammu and Kashmir",
            owner=self.admin,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=True,
            monthly_rate=Decimal("50000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="Launch Campaign",
            code="CMP-001",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            budget=Decimal("200000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Launch",
        )

    def test_campaign_booked_email_sent_once(self):
        booking = BookingService().create(
            actor=self.sales,
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Your Outdoor Media Campaign Has Been Created")
        self.assertIn("https://omms.vercel.app/campaigns/public/", mail.outbox[0].body)
        self.assertEqual(
            EmailNotificationLog.objects.filter(notification_type=EmailNotificationLog.NotificationType.CAMPAIGN_BOOKED).count(),
            1,
        )
        self.assertTrue(booking.campaign.access_tokens.filter(is_active=True).exists())

    def test_campaign_booked_email_not_duplicated(self):
        BookingService().create(
            actor=self.sales,
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )
        second_unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-002",
            face_count=1,
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=False,
            monthly_rate=Decimal("30000.00"),
        )
        BookingService().create(
            actor=self.sales,
            campaign=self.campaign,
            media_unit=second_unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("30000.00"),
            status=Booking.Status.CONFIRMED,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailNotificationLog.objects.filter(event_key=f"campaign_booked:{self.campaign.id}").count(), 1)

    def test_missing_client_email_logs_skipped(self):
        self.client_user.email = ""
        self.client_user.save(update_fields=["email"])

        BookingService().create(
            actor=self.sales,
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )

        log = EmailNotificationLog.objects.get(event_key=f"campaign_booked:{self.campaign.id}")
        self.assertEqual(log.status, EmailNotificationLog.Status.SKIPPED)
        self.assertEqual(len(mail.outbox), 0)

    @patch("apps.notifications.services.send_mail", side_effect=RuntimeError("SMTP unavailable"))
    def test_email_failure_logs_failed_and_booking_creation_survives(self, _send_mail):
        booking = BookingService().create(
            actor=self.sales,
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )

        self.assertIsNotNone(booking.pk)
        log = EmailNotificationLog.objects.get(event_key=f"campaign_booked:{self.campaign.id}")
        self.assertEqual(log.status, EmailNotificationLog.Status.FAILED)
        self.assertIn("SMTP unavailable", log.error_message)

    def test_share_token_is_reused_for_campaign_notifications(self):
        service = NotificationService()
        booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )

        first = service.send_campaign_booked_notification(booking, actor=self.sales)
        second = service.send_campaign_booked_notification(booking, actor=self.sales)

        self.assertTrue(first.log.campaign.access_tokens.filter(is_active=True).exists())
        self.assertFalse(second.created)
        self.assertEqual(first.log.campaign.access_tokens.filter(is_active=True).count(), 1)

    def test_poe_upload_email_sent_once_with_campaign_link(self):
        booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )
        poe = ProofOfExecution.objects.create(
            booking=booking,
            executed_on=date(2025, 4, 10),
        )

        image = self._build_uploaded_image()
        media = ProofOfExecutionMediaService().create(
            actor=self.operations,
            poe_record=poe,
            image=image,
            note="Installed successfully",
        )

        self.assertIsNotNone(media.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Installation Proof Uploaded for Your Campaign")
        self.assertIn("https://omms.vercel.app/campaigns/public/", mail.outbox[0].body)
        self.assertEqual(
            EmailNotificationLog.objects.filter(notification_type=EmailNotificationLog.NotificationType.POE_UPLOADED).count(),
            1,
        )


class NotificationPreferenceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email="admin-pref@example.com", username="admin-pref", password="x", role=User.Role.ADMIN)
        self.operations = User.objects.create_user(email="ops-pref@example.com", username="ops-pref", password="x", role=User.Role.OPERATIONS)
        self.client_user = User.objects.create_user(email="client-pref@example.com", username="client-pref", password="x", role=User.Role.CLIENT)

    def test_user_can_save_and_read_own_notification_preference(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("notification-preferences-list"),
            {
                "user": self.operations.id,
                "notification_type": EmailNotificationLog.NotificationType.EXPORT_COMPLETED,
                "in_app_enabled": False,
                "email_enabled": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data["in_app_enabled"])

        list_response = self.client.get(reverse("notification-preferences-list"))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["results"]), 1)
        self.assertEqual(list_response.data["results"][0]["user"], self.operations.id)

    def test_non_admin_cannot_create_preference_for_another_user(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            reverse("notification-preferences-list"),
            {
                "user": self.operations.id,
                "notification_type": EmailNotificationLog.NotificationType.INVOICE_ISSUED,
                "in_app_enabled": False,
                "email_enabled": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        preference = NotificationPreference.objects.get(notification_type=EmailNotificationLog.NotificationType.INVOICE_ISSUED)
        self.assertEqual(preference.user, self.client_user)

    def test_muted_in_app_preference_filters_role_notifications_from_inbox(self):
        NotificationPreference.objects.create(
            user=self.operations,
            notification_type=EmailNotificationLog.NotificationType.INVENTORY_IMPORT_COMPLETED,
            in_app_enabled=False,
            email_enabled=True,
        )
        Notification.objects.create(
            recipient_role=User.Role.OPERATIONS,
            event_type=EmailNotificationLog.NotificationType.INVENTORY_IMPORT_COMPLETED,
            title="Inventory import completed",
        )
        Notification.objects.create(
            recipient_role=User.Role.OPERATIONS,
            event_type=EmailNotificationLog.NotificationType.EXPORT_COMPLETED,
            title="Export completed",
        )

        self.client.force_authenticate(user=self.operations)
        response = self.client.get(reverse("notifications-inbox-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertNotIn("Inventory import completed", titles)
        self.assertIn("Export completed", titles)

    def test_event_types_include_group_metadata_for_preferences_ui(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.get(reverse("notification-preferences-event-types"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        export_failed = next(item for item in response.data["event_types"] if item["value"] == EmailNotificationLog.NotificationType.EXPORT_FAILED)
        self.assertEqual(export_failed["category"], "Exports")
        self.assertTrue(export_failed["description"])
