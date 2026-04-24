from .base import *  # noqa: F403,F401
from .env import get_bool, get_list

DEBUG = get_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", ["*"])
