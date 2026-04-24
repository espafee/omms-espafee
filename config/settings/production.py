from .base import *  # noqa: F403,F401
from .env import get_bool, get_list

DEBUG = get_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = get_bool("DJANGO_SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = get_bool("DJANGO_CSRF_COOKIE_SECURE", True)
SECURE_SSL_REDIRECT = get_bool("DJANGO_SECURE_SSL_REDIRECT", False)
