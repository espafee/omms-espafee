from .base import *  # noqa: F403,F401
from .env import get_bool, get_int, get_list
from django.core.exceptions import ImproperlyConfigured

DEBUG = get_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

if not DEBUG and SECRET_KEY == "django-insecure-change-me-please-replace-with-a-long-random-secret":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a secure value in production.")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must include at least one host in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = get_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = get_bool("DJANGO_CSRF_COOKIE_SECURE", True)
SECURE_SSL_REDIRECT = get_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = get_int("DJANGO_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = get_bool("DJANGO_HSTS_PRELOAD", False)
