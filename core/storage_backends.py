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
