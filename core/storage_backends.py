from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from storages.backends.s3 import S3Storage


class PublicMediaStorage(S3Storage):
    """
    S3-compatible storage for user-uploaded media.

    Additional provider credentials and URL behavior are injected through
    Django's STORAGES["default"]["OPTIONS"] settings so this backend stays
    reusable across S3, R2, Spaces, and similar providers.
    """

    location = "media"
    file_overwrite = False
    querystring_auth = False


class PrivateDocumentStorage(S3Storage):
    """
    Private S3-compatible storage for sensitive document uploads.

    This backend is intentionally separate from public media storage so invoice
    PDFs, contracts, receipts, and internal documents can only be accessed
    through short-lived signed URLs.
    """

    location = "documents"
    file_overwrite = False
    querystring_auth = True

    def __init__(self, *args, **kwargs):
        options = get_private_document_storage_options()
        options.update(kwargs)
        super().__init__(*args, **options)


def get_private_document_storage_options() -> dict:
    bucket_name = getattr(settings, "AWS_PRIVATE_STORAGE_BUCKET_NAME", "").strip()
    if not bucket_name:
        raise ImproperlyConfigured("AWS_PRIVATE_STORAGE_BUCKET_NAME is required for private document storage.")

    access_key = getattr(settings, "AWS_PRIVATE_ACCESS_KEY_ID", "").strip()
    secret_key = getattr(settings, "AWS_PRIVATE_SECRET_ACCESS_KEY", "").strip()
    region_name = getattr(settings, "AWS_PRIVATE_S3_REGION_NAME", "").strip()
    endpoint_url = getattr(settings, "AWS_PRIVATE_S3_ENDPOINT_URL", "").strip()

    if not access_key or not secret_key:
        raise ImproperlyConfigured(
            "Private document storage requires AWS_PRIVATE_ACCESS_KEY_ID and AWS_PRIVATE_SECRET_ACCESS_KEY "
            "(or their shared fallbacks)."
        )

    return {
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket_name": bucket_name,
        "region_name": region_name or None,
        "endpoint_url": endpoint_url or None,
        "custom_domain": None,
        "default_acl": None,
        "querystring_auth": True,
        "file_overwrite": False,
        "location": "documents",
    }


def build_private_document_signed_url(file_or_name, *, expiry_seconds: int | None = None, storage=None) -> str | None:
    if not file_or_name:
        return None

    name = getattr(file_or_name, "name", file_or_name)
    if not name:
        return None

    resolved_storage = storage or getattr(file_or_name, "storage", None) or PrivateDocumentStorage()
    expiry = expiry_seconds or getattr(settings, "AWS_PRIVATE_SIGNED_URL_EXPIRY_SECONDS", 900)

    try:
        return resolved_storage.url(name, expire=expiry)
    except TypeError:
        return resolved_storage.url(name)
