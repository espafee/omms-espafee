from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.inventory.tests.storage_backends import FakePrivateDocumentStorage
from core.storage_backends import (
    PrivateDocumentStorage,
    PublicMediaStorage,
    build_private_document_signed_url,
    get_private_document_storage_options,
)


@override_settings(
    AWS_ACCESS_KEY_ID="shared-access-key",
    AWS_SECRET_ACCESS_KEY="shared-secret-key",
    AWS_S3_REGION_NAME="auto",
    AWS_S3_ENDPOINT_URL="https://public-r2.example.com",
    AWS_PRIVATE_STORAGE_BUCKET_NAME="private-documents",
    AWS_PRIVATE_S3_ENDPOINT_URL="https://private-r2.example.com",
    AWS_PRIVATE_S3_REGION_NAME="auto",
    AWS_PRIVATE_ACCESS_KEY_ID="private-access-key",
    AWS_PRIVATE_SECRET_ACCESS_KEY="private-secret-key",
    AWS_PRIVATE_SIGNED_URL_EXPIRY_SECONDS=900,
)
class PrivateDocumentStorageTests(SimpleTestCase):
    def test_public_media_storage_remains_public(self):
        self.assertFalse(PublicMediaStorage.querystring_auth)
        self.assertFalse(PublicMediaStorage.file_overwrite)
        self.assertEqual(PublicMediaStorage.location, "media")

    def test_private_document_storage_uses_signed_private_defaults(self):
        storage = PrivateDocumentStorage()

        self.assertTrue(storage.querystring_auth)
        self.assertFalse(storage.file_overwrite)
        self.assertEqual(storage.location, "documents")
        self.assertEqual(storage.bucket_name, "private-documents")
        self.assertEqual(storage.endpoint_url, "https://private-r2.example.com")
        self.assertEqual(storage.region_name, "auto")
        self.assertIsNone(storage.custom_domain)

    def test_private_document_storage_options_use_private_bucket_settings(self):
        options = get_private_document_storage_options()

        self.assertEqual(options["bucket_name"], "private-documents")
        self.assertEqual(options["endpoint_url"], "https://private-r2.example.com")
        self.assertEqual(options["region_name"], "auto")
        self.assertEqual(options["location"], "documents")
        self.assertFalse(options["file_overwrite"])
        self.assertTrue(options["querystring_auth"])
        self.assertIsNone(options["custom_domain"])

    def test_signed_document_url_helper_returns_expiring_private_url(self):
        fake_file = SimpleNamespace(
            name="invoices/INV-2025-26-0001.pdf",
            storage=FakePrivateDocumentStorage(),
        )

        signed_url = build_private_document_signed_url(fake_file)

        self.assertTrue(signed_url.startswith("https://private.example.com/documents/"))
        self.assertIn("signature=test-signature", signed_url)
        self.assertIn("expires=900", signed_url)
        self.assertNotIn(settings.AWS_PRIVATE_SECRET_ACCESS_KEY, signed_url)
        self.assertNotIn(settings.AWS_SECRET_ACCESS_KEY, signed_url)

    def test_signed_document_url_helper_respects_expiry_override(self):
        fake_storage = FakePrivateDocumentStorage()

        signed_url = build_private_document_signed_url("contracts/msa.pdf", expiry_seconds=120, storage=fake_storage)

        self.assertIn("expires=120", signed_url)
