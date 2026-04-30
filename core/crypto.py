from __future__ import annotations

import base64
import hashlib
import json
from typing import Final

from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_NONCE_BYTES: Final[int] = 12


def _get_encryption_key() -> bytes:
    raw_key = getattr(settings, "OMMS_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        raise ImproperlyConfigured("OMMS_ENCRYPTION_KEY is required to encrypt organization SMTP passwords.")
    return hashlib.sha256(raw_key.encode("utf-8")).digest()


def encrypt_text(value: str) -> str:
    if not value:
        return ""

    cipher = AES.new(_get_encryption_key(), AES.MODE_GCM, nonce=get_random_bytes(_NONCE_BYTES))
    ciphertext, tag = cipher.encrypt_and_digest(value.encode("utf-8"))
    payload = {
        "nonce": base64.b64encode(cipher.nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    if not value:
        return ""

    decoded = base64.b64decode(value.encode("ascii"))
    payload = json.loads(decoded.decode("utf-8"))
    cipher = AES.new(
        _get_encryption_key(),
        AES.MODE_GCM,
        nonce=base64.b64decode(payload["nonce"]),
    )
    plaintext = cipher.decrypt_and_verify(
        base64.b64decode(payload["ciphertext"]),
        base64.b64decode(payload["tag"]),
    )
    return plaintext.decode("utf-8")
