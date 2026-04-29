import io
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia

User = get_user_model()


def generate_test_image(name="poe.png", color=(15, 118, 110)):
    file_obj = io.BytesIO()
    image = Image.new("RGB", (32, 32), color=color)
    image.save(file_obj, format="PNG")
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type="image/png")


def generate_large_test_image(name="poe-large.jpg"):
    file_obj = io.BytesIO()
    image = Image.effect_noise((3200, 2400), 96).convert("RGB")
    image.save(file_obj, format="JPEG", quality=96)
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type="image/jpeg")


@override_settings(MEDIA_URL="/media/")
class PoeMediaAPITests(APITestCase):
    def setUp(self):
        self.media_dir = Path(tempfile.mkdtemp(prefix="omms-poe-media-"))
        self.override = override_settings(MEDIA_ROOT=self.media_dir)
        self.override.enable()

        self.password = "TestPass123!"
        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.operations = self._create_user("ops@example.com", "ops_user", User.Role.OPERATIONS)
        self.client_user = self._create_user("client@example.com", "client_user", User.Role.CLIENT)

        self.site = MediaSite.objects.create(
            name="Metro Panel",
            code="SITE-POE-001",
            site_type=MediaSite.SiteType.DIGITAL,
            address="Central Station",
            city="Mumbai",
            state="Maharashtra",
            owner=self.operations,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-POE-001",
            face_count=1,
            width=Decimal("18.00"),
            height=Decimal("9.00"),
            status=MediaUnit.Status.RESERVED,
            is_illuminated=False,
            monthly_rate=Decimal("65000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="POE Campaign",
            code="CMP-POE-001",
            client=self.client_user,
            account_manager=self.admin,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            budget=Decimal("120000.00"),
            status=Campaign.Status.ACTIVE,
            objective="POE evidence test",
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            booked_rate=Decimal("70000.00"),
            status=Booking.Status.CONFIRMED,
        )
        self.poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            checked_by=self.operations,
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def _create_user(self, email, username, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
        )

    def test_operations_can_upload_poe_evidence_image(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("poe-media-list"),
            {
                "poe_record": self.poe.id,
                "image": generate_test_image("poe-evidence.png"),
                "media_type": "image",
                "note": "Installed successfully",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["poe_record"], self.poe.id)
        self.assertEqual(response.data["captured_by"], self.operations.id)
        self.assertIn("/media/poe/", response.data["image_url"])
        self.assertTrue(ProofOfExecutionMedia.objects.filter(pk=response.data["id"]).exists())
        self.assertTrue(Path(ProofOfExecutionMedia.objects.get(pk=response.data["id"]).image.path).exists())

    def test_poe_media_list_is_retrievable(self):
        media = ProofOfExecutionMedia.objects.create(
            poe_record=self.poe,
            image=generate_test_image("poe-existing.png"),
            media_type="image",
            captured_by=self.operations,
            note="Existing proof",
        )

        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(reverse("poe-media-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], media.id)

    def test_client_cannot_upload_poe_evidence(self):
        self.client.force_authenticate(user=self.client_user)

        response = self.client.post(
            reverse("poe-media-list"),
            {
                "poe_record": self.poe.id,
                "image": generate_test_image("poe-client.png"),
                "media_type": "image",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_poe_media_route_accepts_post_and_is_not_shadowed(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("poe-media-list"),
            {
                "poe_record": self.poe.id,
                "image": generate_test_image("poe-route.png"),
                "media_type": "image",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_poe_evidence_images_are_compressed_before_save(self):
        self.client.force_authenticate(user=self.operations)
        original = generate_large_test_image()
        original_size = original.size

        response = self.client.post(
            reverse("poe-media-list"),
            {
                "poe_record": self.poe.id,
                "image": original,
                "media_type": "image",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        saved_media = ProofOfExecutionMedia.objects.get(pk=response.data["id"])
        self.assertLess(saved_media.image.size, original_size)
        self.assertTrue(saved_media.image.name.lower().endswith(".jpg"))
