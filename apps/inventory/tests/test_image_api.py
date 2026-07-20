import io
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaSiteImage, MediaUnit, MediaUnitImage
from apps.inventory.services import MediaSiteImageService

User = get_user_model()


def generate_test_image(name="test.png", color=(15, 118, 110)):
    file_obj = io.BytesIO()
    image = Image.new("RGB", (32, 32), color=color)
    image.save(file_obj, format="PNG")
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type="image/png")


def generate_large_test_image(name="large-test.jpg"):
    file_obj = io.BytesIO()
    image = Image.effect_noise((3200, 2400), 96).convert("RGB")
    image.save(file_obj, format="JPEG", quality=96)
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type="image/jpeg")


def cloudinary_upload_response(public_id="omms/tenants/1/locations/1/generated"):
    return {
        "asset_id": "asset-123",
        "public_id": public_id,
        "version": 1234567890,
        "secure_url": f"https://res.cloudinary.com/demo/image/upload/v1234567890/{public_id}.jpg",
        "resource_type": "image",
        "format": "jpg",
        "width": 1200,
        "height": 800,
        "bytes": 34567,
    }


@override_settings(MEDIA_URL="/media/")
class InventoryImageAPITests(APITestCase):
    def setUp(self):
        self.media_dir = Path(tempfile.mkdtemp(prefix="omms-inventory-media-"))
        self.override = override_settings(MEDIA_ROOT=self.media_dir)
        self.override.enable()

        self.password = "TestPass123!"
        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.operations = self._create_user("ops@example.com", "ops_user", User.Role.OPERATIONS)
        self.sales = self._create_user("sales@example.com", "sales_user", User.Role.SALES)
        self.client_user = self._create_user("client@example.com", "client_user", User.Role.CLIENT)

        self.site = MediaSite.objects.create(
            name="Airport Billboard",
            code="SITE-IMG-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Airport Road",
            city="Pune",
            state="Maharashtra",
            owner=self.operations,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-IMG-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=True,
            monthly_rate=Decimal("50000.00"),
            facing_direction="Toward Jammu City",
            site_type=MediaUnit.SiteType.SINGLE_SIDE,
        )
        self.campaign = Campaign.objects.create(
            name="Image Campaign",
            code="CMP-IMG-001",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Image workflow test",
        )
        Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            booked_rate=Decimal("55000.00"),
            status=Booking.Status.CONFIRMED,
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

    def test_operations_can_upload_site_image(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Front angle",
                "is_primary": True,
                "image": generate_test_image("site-primary.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["site"], self.site.id)
        self.assertTrue(response.data["is_primary"])
        self.assertEqual(response.data["uploaded_by"], self.operations.id)
        self.assertIn("/media/inventory/sites/", response.data["image_url"])
        self.assertTrue(MediaSiteImage.objects.filter(pk=response.data["id"]).exists())
        self.assertTrue(Path(MediaSiteImage.objects.get(pk=response.data["id"]).image.path).exists())

    def test_operations_can_upload_media_unit_image(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-unit-images-list"),
            {
                "media_unit": self.unit.id,
                "caption": "Unit frontage",
                "is_primary": True,
                "image": generate_test_image("unit-primary.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["media_unit"], self.unit.id)
        self.assertTrue(response.data["is_primary"])
        self.assertEqual(response.data["uploaded_by"], self.operations.id)
        self.assertIn("/media/inventory/units/", response.data["image_url"])
        self.assertTrue(MediaUnitImage.objects.filter(pk=response.data["id"]).exists())
        self.assertTrue(Path(MediaUnitImage.objects.get(pk=response.data["id"]).image.path).exists())

    def test_admin_can_publish_and_unpublish_media_units_for_planner(self):
        self.client.force_authenticate(user=self.admin)

        publish_response = self.client.post(
            reverse("inventory-units-bulk-publication"),
            {"unit_ids": [self.unit.id], "is_publicly_listed": True},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(publish_response.data["updated_count"], 1)
        self.unit.refresh_from_db()
        self.assertTrue(self.unit.is_publicly_listed)

        unpublish_response = self.client.post(
            reverse("inventory-units-bulk-publication"),
            {"unit_ids": [self.unit.id], "is_publicly_listed": False},
            format="json",
        )
        self.assertEqual(unpublish_response.status_code, status.HTTP_200_OK)
        self.unit.refresh_from_db()
        self.assertFalse(self.unit.is_publicly_listed)

    @override_settings(MEDIA_PUBLIC_BASE_URL="https://omms-api.onrender.com")
    def test_media_urls_can_use_public_base_override(self):
        image = MediaSiteImage.objects.create(
            site=self.site,
            image=generate_test_image("site-public.png"),
            caption="Public URL",
            uploaded_by=self.operations,
        )

        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(reverse("inventory-sites-detail", args=[self.site.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["primary_image"]["id"], image.id)
        self.assertTrue(response.data["primary_image"]["image_url"].startswith("https://omms-api.onrender.com/media/"))

    @override_settings(
        USE_S3_MEDIA=True,
        MEDIA_PUBLIC_BASE_URL="",
        STORAGES={
            "default": {
                "BACKEND": "apps.inventory.tests.storage_backends.FakePublicMediaStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        },
    )
    def test_media_urls_preserve_public_storage_urls_in_s3_mode(self):
        image = MediaSiteImage.objects.create(
            site=self.site,
            image=generate_test_image("site-s3.png"),
            caption="S3 style URL",
            uploaded_by=self.operations,
        )

        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(reverse("inventory-sites-detail", args=[self.site.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["primary_image"]["id"], image.id)
        self.assertTrue(response.data["primary_image"]["image_url"].startswith("https://cdn.example.com/media/"))

    @override_settings(
        USE_S3_MEDIA=True,
        MEDIA_PUBLIC_BASE_URL="",
        STORAGES={
            "default": {
                "BACKEND": "apps.inventory.tests.storage_backends.FakePublicMediaStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        },
    )
    def test_upload_endpoint_returns_public_storage_url_in_s3_mode(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Public upload URL",
                "image": generate_test_image("site-upload-s3.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["image_url"].startswith("https://cdn.example.com/media/"))

    @override_settings(
        MEDIA_STORAGE_PROVIDER="cloudinary",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
        CLOUDINARY_UPLOAD_PRESET="omms_inventory_signed",
        CLOUDINARY_ROOT_FOLDER="omms",
    )
    @patch("cloudinary.uploader.upload")
    def test_cloudinary_site_image_upload_stores_provider_metadata(self, upload_mock):
        upload_mock.return_value = cloudinary_upload_response("omms/tenants/1/locations/1/site-primary")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Cloudinary primary",
                "image": generate_test_image("cloudinary-site.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        image = MediaSiteImage.objects.get(pk=response.data["id"])
        self.assertEqual(image.provider, "cloudinary")
        self.assertEqual(image.provider_public_id, "omms/tenants/1/locations/1/site-primary")
        self.assertEqual(image.provider_asset_id, "asset-123")
        self.assertEqual(image.width, 1200)
        self.assertEqual(image.height, 800)
        self.assertEqual(image.bytes, 34567)
        self.assertEqual(image.original_filename, "cloudinary-site.png")
        self.assertIsNone(image.image.name or None)
        kwargs = upload_mock.call_args.kwargs
        self.assertEqual(kwargs["upload_preset"], "omms_inventory_signed")
        self.assertEqual(kwargs["folder"], f"omms/tenants/{self.site.tenant_id}/locations/{self.site.id}")
        self.assertEqual(kwargs["resource_type"], "image")
        self.assertNotIn("api-secret", str(response.data))
        self.assertIn("res.cloudinary.com", response.data["image_url"])

    @override_settings(
        MEDIA_STORAGE_PROVIDER="cloudinary",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
        CLOUDINARY_UPLOAD_PRESET="omms_inventory_signed",
        CLOUDINARY_ROOT_FOLDER="omms",
    )
    @patch("cloudinary.uploader.upload")
    def test_cloudinary_unit_image_upload_uses_advertising_unit_folder(self, upload_mock):
        upload_mock.return_value = cloudinary_upload_response("omms/tenants/1/advertising-units/1/unit-primary")
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-unit-images-list"),
            {
                "media_unit": self.unit.id,
                "caption": "Cloudinary unit",
                "image": generate_test_image("cloudinary-unit.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        image = MediaUnitImage.objects.get(pk=response.data["id"])
        self.assertEqual(image.provider, "cloudinary")
        self.assertEqual(upload_mock.call_args.kwargs["folder"], f"omms/tenants/{self.unit.site.tenant_id}/advertising-units/{self.unit.id}")

    @override_settings(
        MEDIA_STORAGE_PROVIDER="cloudinary",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
        CLOUDINARY_UPLOAD_PRESET="omms_inventory_signed",
    )
    @patch("cloudinary.uploader.upload")
    def test_cloudinary_upload_rejects_invalid_file_without_provider_call(self, upload_mock):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Bad",
                "image": SimpleUploadedFile("bad.txt", b"not an image", content_type="text/plain"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        upload_mock.assert_not_called()

    @override_settings(
        MEDIA_STORAGE_PROVIDER="cloudinary",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
        CLOUDINARY_UPLOAD_PRESET="omms_inventory_signed",
    )
    @patch("cloudinary.uploader.upload", side_effect=RuntimeError("provider down"))
    def test_cloudinary_failure_creates_no_database_record(self, upload_mock):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Provider failure",
                "image": generate_test_image("provider-failure.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(MediaSiteImage.objects.filter(caption="Provider failure").exists())
        upload_mock.assert_called_once()

    @override_settings(
        MEDIA_STORAGE_PROVIDER="cloudinary",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
        CLOUDINARY_UPLOAD_PRESET="omms_inventory_signed",
    )
    @patch("cloudinary.uploader.destroy")
    @patch("cloudinary.uploader.upload")
    def test_cloudinary_database_failure_attempts_uploaded_asset_cleanup(self, upload_mock, destroy_mock):
        upload_mock.return_value = cloudinary_upload_response("omms/tenants/1/locations/1/orphan")
        service = MediaSiteImageService()

        with patch.object(MediaSiteImage, "save", side_effect=RuntimeError("db unavailable")):
            with self.assertRaises(RuntimeError):
                service.create(
                    actor=self.operations,
                    site=self.site,
                    caption="Cleanup",
                    image=generate_test_image("cleanup.png"),
                )

        destroy_mock.assert_called_once_with("omms/tenants/1/locations/1/orphan", resource_type="image", invalidate=True)

    @override_settings(
        MEDIA_STORAGE_PROVIDER="cloudinary",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
        CLOUDINARY_UPLOAD_PRESET="omms_inventory_signed",
    )
    @patch("cloudinary.uploader.destroy")
    @patch("cloudinary.uploader.upload")
    def test_cloudinary_replacement_uploads_new_image_before_deleting_old_asset(self, upload_mock, destroy_mock):
        upload_mock.return_value = cloudinary_upload_response("omms/tenants/1/locations/1/replacement")
        existing = MediaSiteImage.objects.create(
            site=self.site,
            caption="Old cloudinary",
            provider="cloudinary",
            provider_public_id="omms/tenants/1/locations/1/old",
            secure_url="https://res.cloudinary.com/demo/image/upload/v1/old.jpg",
            uploaded_by=self.operations,
        )
        self.client.force_authenticate(user=self.operations)

        response = self.client.patch(
            reverse("inventory-site-images-detail", args=[existing.id]),
            {"image": generate_test_image("replacement.png")},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        existing.refresh_from_db()
        self.assertEqual(existing.provider_public_id, "omms/tenants/1/locations/1/replacement")
        upload_mock.assert_called_once()
        destroy_mock.assert_called_once_with("omms/tenants/1/locations/1/old", resource_type="image", invalidate=True)

    @override_settings(
        MEDIA_STORAGE_PROVIDER="r2",
        CLOUDINARY_URL="cloudinary://api-key:api-secret@demo",
    )
    @patch("cloudinary.uploader.destroy")
    def test_cloudinary_delete_uses_record_provider_even_when_active_provider_is_r2(self, destroy_mock):
        image = MediaSiteImage.objects.create(
            site=self.site,
            caption="Cloudinary delete",
            provider="cloudinary",
            provider_public_id="omms/tenants/1/locations/1/delete-me",
            secure_url="https://res.cloudinary.com/demo/image/upload/v1/delete-me.jpg",
            uploaded_by=self.operations,
        )
        self.client.force_authenticate(user=self.operations)

        response = self.client.delete(reverse("inventory-site-images-detail", args=[image.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        destroy_mock.assert_called_once_with("omms/tenants/1/locations/1/delete-me", resource_type="image", invalidate=True)
        self.assertFalse(MediaSiteImage.objects.filter(pk=image.id).exists())

    def test_site_detail_exposes_primary_image_and_gallery(self):
        first = MediaSiteImage.objects.create(
            site=self.site,
            image=generate_test_image("site-one.png"),
            caption="One",
            is_primary=True,
            uploaded_by=self.operations,
        )
        second = MediaSiteImage.objects.create(
            site=self.site,
            image=generate_test_image("site-two.png", color=(180, 83, 9)),
            caption="Two",
            is_primary=False,
            uploaded_by=self.operations,
        )

        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(reverse("inventory-sites-detail", args=[self.site.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["primary_image"]["id"], first.id)
        self.assertEqual(len(response.data["image_gallery"]), 2)
        self.assertEqual({item["id"] for item in response.data["image_gallery"]}, {first.id, second.id})

    def test_marking_new_site_image_primary_unsets_previous_primary(self):
        first = MediaSiteImage.objects.create(
            site=self.site,
            image=generate_test_image("site-first.png"),
            caption="First",
            is_primary=True,
            uploaded_by=self.operations,
        )
        second = MediaSiteImage.objects.create(
            site=self.site,
            image=generate_test_image("site-second.png"),
            caption="Second",
            is_primary=False,
            uploaded_by=self.operations,
        )

        self.client.force_authenticate(user=self.operations)
        response = self.client.patch(
            reverse("inventory-site-images-detail", args=[second.id]),
            {"is_primary": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)

    def test_sales_cannot_upload_site_image(self):
        self.client.force_authenticate(user=self.sales)

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Unauthorized",
                "image": generate_test_image("unauthorized.png"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_site(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("inventory-sites-list"),
            {
                "name": "Ring Road Gantry",
                "code": "SITE-NEW-001",
                "site_type": MediaSite.SiteType.DIGITAL,
                "address": "Outer Ring Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "latitude": "12.971600",
                "longitude": "77.594600",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "SITE-NEW-001")
        self.assertEqual(response.data["owner"], self.admin.id)
        self.assertEqual(response.data["location_status"], MediaSite.LocationStatus.VERIFIED)
        self.assertEqual(response.data["location_source"], MediaSite.LocationSource.ADMIN_VERIFIED)

    def test_admin_can_create_site_without_coordinates(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("inventory-sites-list"),
            {
                "name": "POE Located Gantry",
                "code": "SITE-POE-GPS-001",
                "site_type": MediaSite.SiteType.BILLBOARD,
                "address": "First POE capture road",
                "city": "Bengaluru",
                "state": "Karnataka",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["latitude"])
        self.assertIsNone(response.data["longitude"])
        self.assertEqual(response.data["location_status"], MediaSite.LocationStatus.UNVERIFIED)
        self.assertEqual(response.data["location_source"], "")

    def test_operations_cannot_create_site(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-sites-list"),
            {
                "name": "Unauthorized Site",
                "code": "SITE-NOPE-001",
                "site_type": MediaSite.SiteType.BILLBOARD,
                "address": "Restricted",
                "city": "Pune",
                "state": "Maharashtra",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_site_without_active_bookings(self):
        deletable_site = MediaSite.objects.create(
            name="Quiet Corner",
            code="SITE-DELETE-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Service Road",
            city="Pune",
            state="Maharashtra",
            owner=self.admin,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(reverse("inventory-sites-detail", args=[deletable_site.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MediaSite.objects.filter(id=deletable_site.id).exists())

    def test_admin_cannot_delete_site_with_active_bookings(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(reverse("inventory-sites-detail", args=[self.site.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active bookings", str(response.data).lower())

    def test_operations_cannot_delete_site(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.delete(reverse("inventory-sites-detail", args=[self.site.id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unit_detail_exposes_primary_image(self):
        primary = MediaUnitImage.objects.create(
            media_unit=self.unit,
            image=generate_test_image("unit-primary.png"),
            caption="Primary",
            is_primary=True,
            uploaded_by=self.operations,
        )

        self.client.force_authenticate(user=self.client_user)
        response = self.client.get(reverse("inventory-units-detail", args=[self.unit.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["primary_image"]["id"], primary.id)
        self.assertEqual(len(response.data["image_gallery"]), 1)
        self.assertEqual(response.data["facing_direction"], "Toward Jammu City")
        self.assertEqual(response.data["site_type"], MediaUnit.SiteType.SINGLE_SIDE)

    def test_operations_can_create_media_unit_with_direction_and_type(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.post(
            reverse("inventory-units-list"),
            {
                "site": self.site.id,
                "unit_code": "UNIT-IMG-002",
                "face_count": 1,
                "width": "18.00",
                "height": "9.00",
                "status": MediaUnit.Status.AVAILABLE,
                "is_illuminated": False,
                "monthly_rate": "45000.00",
                "facing_direction": "Toward Lakhanpur",
                "site_type": MediaUnit.SiteType.BOTH_SIDE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["facing_direction"], "Toward Lakhanpur")
        self.assertEqual(response.data["site_type"], MediaUnit.SiteType.BOTH_SIDE)

    def test_operations_can_update_media_unit_direction_and_type(self):
        self.client.force_authenticate(user=self.operations)

        response = self.client.patch(
            reverse("inventory-units-detail", args=[self.unit.id]),
            {
                "facing_direction": "Toward SIDCO Chowk",
                "site_type": MediaUnit.SiteType.BOTH_SIDE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["facing_direction"], "Toward SIDCO Chowk")
        self.assertEqual(response.data["site_type"], MediaUnit.SiteType.BOTH_SIDE)

    def test_uploaded_images_are_compressed_before_save(self):
        self.client.force_authenticate(user=self.operations)
        original = generate_large_test_image()
        original_size = original.size

        response = self.client.post(
            reverse("inventory-site-images-list"),
            {
                "site": self.site.id,
                "caption": "Compressed shot",
                "image": original,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        saved_image = MediaSiteImage.objects.get(pk=response.data["id"])
        self.assertLess(saved_image.image.size, original_size)
        self.assertTrue(saved_image.image.name.lower().endswith(".jpg"))

    def test_media_unit_list_supports_type_and_city_filters(self):
        MediaUnit.objects.create(
            site=MediaSite.objects.create(
                name="SIDCO Corner",
                code="SITE-IMG-002",
                site_type=MediaSite.SiteType.BILLBOARD,
                address="SIDCO Chowk",
                city="Jammu",
                state="Jammu and Kashmir",
                owner=self.operations,
            ),
            unit_code="UNIT-IMG-099",
            face_count=1,
            width=Decimal("18.00"),
            height=Decimal("9.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=False,
            monthly_rate=Decimal("42000.00"),
            facing_direction="Toward Lakhanpur",
            site_type=MediaUnit.SiteType.BOTH_SIDE,
        )

        self.client.force_authenticate(user=self.sales)
        response = self.client.get(
            reverse("inventory-units-list"),
            {
                "site_type": MediaUnit.SiteType.SINGLE_SIDE,
                "site__city": "Pune",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.unit.id)

    def test_all_sites_list_exposes_structured_unit_and_site_fields(self):
        unit_image = MediaUnitImage.objects.create(
            media_unit=self.unit,
            image=generate_test_image("unit-list-primary.png"),
            caption="List thumbnail",
            is_primary=True,
            uploaded_by=self.operations,
        )
        empty_site = MediaSite.objects.create(
            name="New Site Awaiting Units",
            code="SITE-EMPTY-001",
            site_type=MediaSite.SiteType.TRANSIT,
            address="Depot Road",
            city="Pune",
            state="Maharashtra",
            owner=self.operations,
        )

        self.client.force_authenticate(user=self.sales)
        response = self.client.get(reverse("inventory-sites-all-sites"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        row = next(item for item in response.data["results"] if item["site_id"] == self.site.id)
        self.assertEqual(row["id"], self.site.id)
        self.assertEqual(row["site_id"], self.site.id)
        self.assertEqual(row["site_code"], self.site.code)
        self.assertEqual(row["unit_ids"], [self.unit.id])
        self.assertEqual(row["unit_codes"], [self.unit.unit_code])
        self.assertEqual(row["title"], self.site.name)
        self.assertEqual(row["address"], self.site.address)
        self.assertEqual(row["city"], self.site.city)
        self.assertEqual(row["state"], self.site.state)
        self.assertEqual(row["media_type"], self.site.site_type)
        self.assertEqual(row["dimensions"], "20.00 x 10.00")
        self.assertEqual(row["facing_direction"], "Toward Jammu City")
        self.assertEqual(row["unit_site_type"], MediaUnit.SiteType.SINGLE_SIDE)
        self.assertEqual(row["status"], MediaUnit.Status.AVAILABLE)
        self.assertIn("/media/inventory/units/", row["thumbnail_url"])
        self.assertNotIn("documents/", row["thumbnail_url"])
        self.assertEqual(unit_image.id, self.unit.primary_image_object.id)
        empty_row = next(item for item in response.data["results"] if item["site_id"] == empty_site.id)
        self.assertEqual(empty_row["status"], "no_units")
        self.assertEqual(empty_row["unit_ids"], [])
        self.assertEqual(empty_row["unit_codes"], [])

    def test_all_sites_list_supports_filters_search_and_pagination(self):
        other_site = MediaSite.objects.create(
            name="SIDCO Corner",
            code="SITE-IMG-002",
            site_type=MediaSite.SiteType.DIGITAL,
            address="SIDCO Chowk",
            city="Jammu",
            state="Jammu and Kashmir",
            latitude=Decimal("32.726600"),
            longitude=Decimal("74.857000"),
            owner=self.operations,
        )
        MediaSiteImage.objects.create(
            site=other_site,
            image=generate_test_image("site-filter-primary.png"),
            is_primary=True,
            uploaded_by=self.operations,
        )
        other_unit = MediaUnit.objects.create(
            site=other_site,
            unit_code="UNIT-IMG-099",
            face_count=2,
            width=Decimal("18.00"),
            height=Decimal("9.00"),
            status=MediaUnit.Status.RESERVED,
            is_illuminated=False,
            monthly_rate=Decimal("42000.00"),
            facing_direction="Toward Lakhanpur",
            site_type=MediaUnit.SiteType.BOTH_SIDE,
        )

        self.client.force_authenticate(user=self.sales)
        response = self.client.get(
            reverse("inventory-sites-all-sites"),
            {
                "city": "Jammu",
                "status": MediaUnit.Status.RESERVED,
                "media_type": MediaSite.SiteType.DIGITAL,
                "facing_direction": "Toward Lakhanpur",
                "site_type": MediaUnit.SiteType.BOTH_SIDE,
                "photo_status": "with_photos",
                "coordinate_status": "coordinates_set",
                "search": "SIDCO",
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["site_id"], other_site.id)
        self.assertEqual(response.data["results"][0]["unit_ids"], [other_unit.id])
        self.assertEqual(response.data["results"][0]["city"], "Jammu")

    def test_all_units_list_exposes_location_summary_filters_and_safe_thumbnail(self):
        unit_image = MediaUnitImage.objects.create(
            media_unit=self.unit,
            image=generate_test_image("unit-summary.png"),
            caption="Sellable face",
            is_primary=True,
            uploaded_by=self.operations,
        )

        self.client.force_authenticate(user=self.sales)
        response = self.client.get(
            reverse("inventory-units-all-units"),
            {
                "search": "Airport",
                "city": "Pune",
                "status": MediaUnit.Status.AVAILABLE,
                "site_type": MediaUnit.SiteType.SINGLE_SIDE,
                "facing_direction": "Jammu",
                "is_illuminated": "true",
                "size": "20.00x10.00",
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["id"], self.unit.id)
        self.assertEqual(row["unit_code"], self.unit.unit_code)
        self.assertEqual(row["location_id"], self.site.id)
        self.assertEqual(row["location_name"], self.site.name)
        self.assertEqual(row["location_code"], self.site.code)
        self.assertEqual(row["city"], self.site.city)
        self.assertEqual(row["image_count"], 1)
        self.assertIn("/media/inventory/units/", row["thumbnail_url"])
        self.assertNotIn("documents/", row["thumbnail_url"])
        self.assertEqual(unit_image.id, self.unit.primary_image_object.id)
