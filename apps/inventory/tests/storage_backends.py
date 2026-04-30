from django.core.files.storage import FileSystemStorage


class FakePublicMediaStorage(FileSystemStorage):
    def url(self, name):
        normalized_name = str(name).lstrip("/")
        return f"https://cdn.example.com/media/{normalized_name}"


class FakePrivateDocumentStorage(FileSystemStorage):
    querystring_auth = True
    file_overwrite = False
    location = "documents"

    def url(self, name, expire=None):
        normalized_name = str(name).lstrip("/")
        expiry = 900 if expire is None else int(expire)
        return f"https://private.example.com/documents/{normalized_name}?signature=test-signature&expires={expiry}"
