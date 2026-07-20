from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import APIException

from core.images import build_public_media_url


SUPPORTED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}
SUPPORTED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class MediaStorageError(APIException):
    status_code = 502
    default_detail = "Image storage provider failed. Please try again."
    default_code = "media_storage_error"


@dataclass(frozen=True)
class UploadedImage:
    provider: str
    provider_asset_id: str = ""
    provider_public_id: str = ""
    provider_version: str = ""
    secure_url: str = ""
    resource_type: str = "image"
    format: str = ""
    width: int | None = None
    height: int | None = None
    bytes: int | None = None
    original_filename: str = ""


class BaseImageStorageProvider:
    provider_name = "base"

    def validate_configuration(self) -> None:
        return None

    def upload_image(self, file_obj, *, folder: str, metadata: dict[str, Any] | None = None) -> UploadedImage:
        raise NotImplementedError

    def delete_image(self, image_record) -> None:
        raise NotImplementedError

    def build_delivery_url(self, image_record, *, variant: str = "original", request=None) -> str | None:
        raise NotImplementedError


class R2ImageStorageProvider(BaseImageStorageProvider):
    provider_name = "r2"

    def delete_image(self, image_record) -> None:
        image = getattr(image_record, "image", None)
        if image:
            image.delete(save=False)

    def build_delivery_url(self, image_record, *, variant: str = "original", request=None) -> str | None:
        return build_public_media_url(getattr(image_record, "image", None), request=request)


class CloudinaryImageStorageProvider(BaseImageStorageProvider):
    provider_name = "cloudinary"

    VARIANTS = {
        "inventory_thumbnail": {"crop": "fill", "width": 320, "height": 220, "fetch_format": "auto", "quality": "auto"},
        "planner_card": {"crop": "fill", "width": 900, "height": 600, "fetch_format": "auto", "quality": "auto"},
        "full_preview": {"crop": "limit", "width": 1800, "fetch_format": "auto", "quality": "auto"},
    }

    def validate_configuration(self) -> None:
        missing = []
        if not getattr(settings, "CLOUDINARY_URL", ""):
            missing.append("CLOUDINARY_URL")
        if not getattr(settings, "CLOUDINARY_UPLOAD_PRESET", ""):
            missing.append("CLOUDINARY_UPLOAD_PRESET")
        if missing:
            raise ImproperlyConfigured(
                "MEDIA_STORAGE_PROVIDER=cloudinary requires " + ", ".join(missing) + "."
            )

    def upload_image(self, file_obj, *, folder: str, metadata: dict[str, Any] | None = None) -> UploadedImage:
        self.validate_configuration()
        validate_upload_image(file_obj)
        try:
            import cloudinary
            import cloudinary.uploader
        except ImportError as exc:
            raise ImproperlyConfigured("Install the cloudinary Python package to use Cloudinary media storage.") from exc

        configure_cloudinary_sdk(cloudinary)
        file_obj.seek(0)
        try:
            response = cloudinary.uploader.upload(
                file_obj,
                resource_type="image",
                upload_preset=settings.CLOUDINARY_UPLOAD_PRESET,
                folder=folder,
                overwrite=False,
                use_filename=False,
                unique_filename=True,
                context=metadata or {},
            )
        except Exception as exc:
            raise MediaStorageError("Cloudinary image upload failed.") from exc

        required = ("asset_id", "public_id", "secure_url", "width", "height", "format", "bytes")
        missing = [key for key in required if not response.get(key)]
        if missing:
            raise MediaStorageError("Cloudinary upload response was missing: " + ", ".join(missing))

        return UploadedImage(
            provider=self.provider_name,
            provider_asset_id=str(response.get("asset_id") or ""),
            provider_public_id=str(response.get("public_id") or ""),
            provider_version=str(response.get("version") or ""),
            secure_url=str(response.get("secure_url") or ""),
            resource_type=str(response.get("resource_type") or "image"),
            format=str(response.get("format") or ""),
            width=int(response["width"]),
            height=int(response["height"]),
            bytes=int(response["bytes"]),
            original_filename=getattr(file_obj, "name", "") or "",
        )

    def delete_image(self, image_record) -> None:
        public_id = getattr(image_record, "provider_public_id", "")
        if not public_id:
            return
        self.validate_configuration()
        try:
            import cloudinary
            import cloudinary.uploader
        except ImportError as exc:
            raise ImproperlyConfigured("Install the cloudinary Python package to use Cloudinary media storage.") from exc
        configure_cloudinary_sdk(cloudinary)
        cloudinary.uploader.destroy(public_id, resource_type="image", invalidate=True)

    def build_delivery_url(self, image_record, *, variant: str = "original", request=None) -> str | None:
        public_id = getattr(image_record, "provider_public_id", "")
        if not public_id:
            return getattr(image_record, "secure_url", "") or None
        try:
            import cloudinary
            import cloudinary.utils
        except ImportError:
            return getattr(image_record, "secure_url", "") or None
        configure_cloudinary_sdk(cloudinary)
        options = {"secure": True, "resource_type": "image"}
        version = getattr(image_record, "provider_version", "")
        if version:
            options["version"] = version
        transformation = self.VARIANTS.get(variant)
        if transformation:
            options["transformation"] = [transformation]
        return cloudinary.utils.cloudinary_url(public_id, **options)[0]


def get_media_storage_provider() -> BaseImageStorageProvider:
    provider = getattr(settings, "MEDIA_STORAGE_PROVIDER", "r2").strip().lower()
    if provider in {"", "r2", "s3"}:
        return R2ImageStorageProvider()
    if provider == "cloudinary":
        return CloudinaryImageStorageProvider()
    raise ImproperlyConfigured(f"Unsupported MEDIA_STORAGE_PROVIDER: {provider}")


def get_media_storage_provider_for_record(image_record) -> BaseImageStorageProvider:
    provider = getattr(image_record, "provider", "r2")
    if provider == "cloudinary":
        return CloudinaryImageStorageProvider()
    return R2ImageStorageProvider()


def configure_cloudinary_sdk(cloudinary_module) -> None:
    parsed = urlparse(getattr(settings, "CLOUDINARY_URL", ""))
    if parsed.scheme != "cloudinary" or not parsed.hostname:
        raise ImproperlyConfigured("CLOUDINARY_URL must use the cloudinary://<key>:<secret>@<cloud-name> format.")
    cloudinary_module.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username or "",
        api_secret=parsed.password or "",
        secure=True,
    )


def build_storage_folder(*, tenant_id: int | None, entity_kind: str, entity_id: int | None) -> str:
    root = getattr(settings, "CLOUDINARY_ROOT_FOLDER", "omms").strip().strip("/") or "omms"
    tenant_part = tenant_id if tenant_id is not None else "unknown"
    entity_part = entity_id if entity_id is not None else "pending"
    return f"{root}/tenants/{tenant_part}/{entity_kind}/{entity_part}"


def validate_upload_image(file_obj) -> None:
    if not file_obj:
        raise ValidationError("Select an image to upload.")
    size = getattr(file_obj, "size", 0) or 0
    if size <= 0:
        raise ValidationError("Uploaded image is empty.")
    if size > MAX_UPLOAD_BYTES:
        raise ValidationError("Uploaded image must be 10 MB or smaller.")
    extension = Path(getattr(file_obj, "name", "")).suffix.lower().lstrip(".")
    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValidationError("Upload a JPG, PNG, WebP, HEIC, or HEIF image.")
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    if content_type and content_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
        raise ValidationError("Upload a supported image file.")
    if extension in {"heic", "heif"} or content_type in {"image/heic", "image/heif"}:
        return
    position = file_obj.tell() if hasattr(file_obj, "tell") else None
    try:
        file_obj.seek(0)
        with Image.open(file_obj) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Uploaded file is not a valid image.") from exc
    finally:
        if position is not None:
            file_obj.seek(position)


def apply_uploaded_metadata(instance, uploaded: UploadedImage) -> None:
    instance.provider = uploaded.provider
    instance.provider_asset_id = uploaded.provider_asset_id
    instance.provider_public_id = uploaded.provider_public_id
    instance.provider_version = uploaded.provider_version
    instance.secure_url = uploaded.secure_url
    instance.resource_type = uploaded.resource_type
    instance.format = uploaded.format
    instance.width = uploaded.width
    instance.height = uploaded.height
    instance.bytes = uploaded.bytes
    instance.original_filename = uploaded.original_filename
