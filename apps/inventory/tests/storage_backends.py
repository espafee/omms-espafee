from django.core.files.storage import FileSystemStorage


class FakePublicMediaStorage(FileSystemStorage):
    def url(self, name):
        normalized_name = str(name).lstrip("/")
        return f"https://cdn.example.com/media/{normalized_name}"
