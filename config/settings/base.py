from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab

from .env import get_bool, get_database_config, get_env, get_int, get_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = get_env("DJANGO_SECRET_KEY", "django-insecure-change-me-please-replace-with-a-long-random-secret")
DEBUG = get_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = get_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])
CORS_ALLOWED_ORIGINS = get_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    ["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_ALLOW_CREDENTIALS = get_bool("DJANGO_CORS_ALLOW_CREDENTIALS", True)

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "django_filters",
    "rest_framework_simplejwt",
    "drf_spectacular",
]

LOCAL_APPS = [
    "core",
    "apps.users",
    "apps.inventory",
    "apps.bookings",
    "apps.campaigns",
    "apps.poe",
    "apps.billing",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": get_database_config(BASE_DIR)
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Calcutta"
USE_I18N = True
USE_TZ = True

STATIC_URL = get_env("DJANGO_STATIC_URL", "/static/")
STATIC_ROOT = BASE_DIR / get_env("DJANGO_STATIC_ROOT", "staticfiles")
MEDIA_URL = get_env("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / get_env("DJANGO_MEDIA_ROOT", "media")
DEFAULT_FILE_STORAGE_BACKEND = get_env("DJANGO_DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage")
STATICFILES_STORAGE_BACKEND = get_env(
    "DJANGO_STATICFILES_STORAGE",
    "django.contrib.staticfiles.storage.StaticFilesStorage",
)

STORAGES = {
    "default": {
        "BACKEND": DEFAULT_FILE_STORAGE_BACKEND,
    },
    "staticfiles": {
        "BACKEND": STATICFILES_STORAGE_BACKEND,
    },
}

AWS_STORAGE_BUCKET_NAME = get_env("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_REGION_NAME = get_env("AWS_S3_REGION_NAME", "")
AWS_S3_ENDPOINT_URL = get_env("AWS_S3_ENDPOINT_URL", "")
AWS_S3_CUSTOM_DOMAIN = get_env("AWS_S3_CUSTOM_DOMAIN", "")
AWS_DEFAULT_ACL = get_env("AWS_DEFAULT_ACL", "")
AWS_QUERYSTRING_AUTH = get_bool("AWS_QUERYSTRING_AUTH", True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=get_int("JWT_ACCESS_TOKEN_MINUTES", 60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=get_int("JWT_REFRESH_TOKEN_DAYS", 7)),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": get_env("API_DOCS_TITLE", "Outdoor Media Management API"),
    "DESCRIPTION": get_env(
        "API_DOCS_DESCRIPTION",
        "REST API for users, inventory, bookings, campaigns, proof of execution, and billing.",
    ),
    "VERSION": get_env("API_DOCS_VERSION", "1.0.0"),
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
    },
    "COMPONENT_SPLIT_REQUEST": True,
}

CELERY_BROKER_URL = get_env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = get_env("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "mark-overdue-invoices-nightly": {
        "task": "apps.billing.tasks.mark_overdue_invoices",
        "schedule": crontab(hour=get_int("CELERY_OVERDUE_CHECK_HOUR", 1), minute=0),
    }
}
