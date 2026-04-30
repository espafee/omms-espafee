from __future__ import annotations

from django.core.files.base import ContentFile


class MemoryPrivateDocumentStorage:
    saved_files: dict[str, bytes] = {}

    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def reset(cls):
        cls.saved_files = {}

    def save(self, name, content, max_length=None):
        data = content.read() if hasattr(content, "read") else bytes(content)
        self.__class__.saved_files[name] = data
        return name

    def exists(self, name):
        return name in self.__class__.saved_files

    def delete(self, name):
        self.__class__.saved_files.pop(name, None)

    def open(self, name, mode="rb"):
        return ContentFile(self.__class__.saved_files[name], name=name)

    def url(self, name, expire=None):
        expiry = 900 if expire is None else int(expire)
        normalized_name = str(name).lstrip("/")
        return f"https://private.example.com/documents/{normalized_name}?signature=test-signature&expires={expiry}"
