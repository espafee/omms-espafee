from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

IMAGE_QUALITY = 80
MAX_IMAGE_DIMENSION = 2400
LOCAL_MEDIA_STORAGE_BACKEND = "django.core.files.storage.FileSystemStorage"


def is_local_media_storage_backend(backend_path: str | None) -> bool:
    return backend_path == LOCAL_MEDIA_STORAGE_BACKEND


def build_public_media_url(file_field, request=None) -> str | None:
    if not file_field:
        return None

    try:
        file_url = file_field.url
    except ValueError:
        return None

    if not file_url:
        return None

    if file_url.startswith(("http://", "https://")):
        return file_url

    public_base = getattr(settings, "MEDIA_PUBLIC_BASE_URL", "").strip()
    if public_base:
        return urljoin(f"{public_base.rstrip('/')}/", file_url.lstrip("/"))

    if request:
        return request.build_absolute_uri(file_url)

    return file_url


def compress_field_image(field_file, *, quality: int = IMAGE_QUALITY, max_dimension: int = MAX_IMAGE_DIMENSION) -> None:
    if not field_file or getattr(field_file, "_committed", False):
        return

    field_file.file.seek(0)
    with Image.open(field_file.file) as image:
        image = ImageOps.exif_transpose(image)
        has_transparency = _image_has_transparency(image)

        if max(image.size) > max_dimension:
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        if has_transparency:
            if image.mode not in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
            content, extension = _save_png(image)
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            content, extension = _save_jpeg(image, quality=quality)

    filename = f"{Path(field_file.name).stem or 'image'}{extension}"
    field_file.save(filename, content, save=False)


def _image_has_transparency(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA"):
        return True
    return image.mode == "P" and "transparency" in image.info


def _save_png(image: Image.Image) -> tuple[ContentFile, str]:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True, compress_level=6)
    return ContentFile(buffer.getvalue()), ".png"


def _save_jpeg(image: Image.Image, *, quality: int) -> tuple[ContentFile, str]:
    buffer = BytesIO()
    image.save(
        buffer,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )
    return ContentFile(buffer.getvalue()), ".jpg"
