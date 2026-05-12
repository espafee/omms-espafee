from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from .env import get_bool, get_database_config, get_env, get_int, get_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = get_env("DJANGO_SECRET_KEY", "django-insecure-change-me-please-replace-with-a-long-random-secret")
DEBUG = get_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = get_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])
CORS_ALLOWED_ORIGINS = get_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
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
    "apps.issues",
    "apps.billing",
    "apps.notifications",
    "apps.setup",
    "apps.mobile",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

# Local development keeps using filesystem media under MEDIA_ROOT. Production can
# opt into S3-compatible object storage by setting USE_S3_MEDIA=true together with
# the provider credentials below.
MEDIA_URL = get_env("DJANGO_MEDIA_URL", "/media/")
MEDIA_ROOT = BASE_DIR / get_env("DJANGO_MEDIA_ROOT", "media")
MEDIA_PUBLIC_BASE_URL = get_env("DJANGO_MEDIA_PUBLIC_BASE_URL", "")
USE_S3_MEDIA = get_bool("USE_S3_MEDIA", False)
DEFAULT_FILE_STORAGE_BACKEND = get_env("DJANGO_DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage")
STATICFILES_STORAGE_BACKEND = get_env(
    "DJANGO_STATICFILES_STORAGE",
    "django.contrib.staticfiles.storage.StaticFilesStorage",
)

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

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
AWS_S3_OBJECT_PARAMETERS_CACHE_CONTROL = get_env("AWS_S3_OBJECT_PARAMETERS_CACHE_CONTROL", "")
AWS_PRIVATE_STORAGE_BUCKET_NAME = get_env("AWS_PRIVATE_STORAGE_BUCKET_NAME", "")
AWS_PRIVATE_S3_ENDPOINT_URL = get_env("AWS_PRIVATE_S3_ENDPOINT_URL", AWS_S3_ENDPOINT_URL)
AWS_PRIVATE_S3_REGION_NAME = get_env("AWS_PRIVATE_S3_REGION_NAME", AWS_S3_REGION_NAME)
AWS_PRIVATE_ACCESS_KEY_ID = get_env("AWS_PRIVATE_ACCESS_KEY_ID", get_env("AWS_ACCESS_KEY_ID", ""))
AWS_PRIVATE_SECRET_ACCESS_KEY = get_env("AWS_PRIVATE_SECRET_ACCESS_KEY", get_env("AWS_SECRET_ACCESS_KEY", ""))
AWS_PRIVATE_SIGNED_URL_EXPIRY_SECONDS = get_int("AWS_PRIVATE_SIGNED_URL_EXPIRY_SECONDS", 900)

if USE_S3_MEDIA or AWS_PRIVATE_STORAGE_BUCKET_NAME:
    THIRD_PARTY_APPS.append("storages")
    INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

if USE_S3_MEDIA:
    required_s3_settings = {
        "AWS_ACCESS_KEY_ID": get_env("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": get_env("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_STORAGE_BUCKET_NAME": AWS_STORAGE_BUCKET_NAME,
        "AWS_S3_REGION_NAME": AWS_S3_REGION_NAME,
        "AWS_S3_ENDPOINT_URL": AWS_S3_ENDPOINT_URL,
    }
    missing_s3_settings = [name for name, value in required_s3_settings.items() if not value]
    if missing_s3_settings:
        raise ImproperlyConfigured(
            "USE_S3_MEDIA is enabled, but the following settings are missing: "
            + ", ".join(missing_s3_settings)
        )

    s3_media_options = {
        "access_key": required_s3_settings["AWS_ACCESS_KEY_ID"] or None,
        "secret_key": required_s3_settings["AWS_SECRET_ACCESS_KEY"] or None,
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": AWS_S3_REGION_NAME or None,
        "endpoint_url": AWS_S3_ENDPOINT_URL or None,
        "custom_domain": AWS_S3_CUSTOM_DOMAIN or None,
        "default_acl": AWS_DEFAULT_ACL or None,
        "querystring_auth": False,
        "file_overwrite": False,
        "location": "media",
    }

    if AWS_S3_OBJECT_PARAMETERS_CACHE_CONTROL:
        s3_media_options["object_parameters"] = {
            "CacheControl": AWS_S3_OBJECT_PARAMETERS_CACHE_CONTROL,
        }

    STORAGES["default"] = {
        "BACKEND": "core.storage_backends.PublicMediaStorage",
        "OPTIONS": s3_media_options,
    }

PRIVATE_DOCUMENT_STORAGE_BACKEND = get_env(
    "DJANGO_PRIVATE_DOCUMENT_STORAGE",
    "core.storage_backends.PrivateDocumentStorage",
)

FRONTEND_PUBLIC_BASE_URL = get_env("FRONTEND_PUBLIC_BASE_URL", "http://localhost:3000")
NOTIFICATION_COMPANY_NAME = get_env("NOTIFICATION_COMPANY_NAME", "OMMS Control")
OMMS_ENCRYPTION_KEY = get_env("OMMS_ENCRYPTION_KEY", "")

EMAIL_BACKEND = get_env(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = get_env("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_HOST = get_env("EMAIL_HOST", "localhost")
EMAIL_PORT = get_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = get_env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = get_env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = get_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = get_bool("EMAIL_USE_SSL", False)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
BILLING_DEFAULT_GST_RATE = get_env("BILLING_DEFAULT_GST_RATE", "")
BILLING_GST_RATE_BY_SAC = get_env("BILLING_GST_RATE_BY_SAC", "")
POE_REVIEW_SLA_HOURS = get_int("POE_REVIEW_SLA_HOURS", 24)
OMMS_PUBLIC_REGISTRATION_ENABLED = get_bool("OMMS_PUBLIC_REGISTRATION_ENABLED", False)
AUTH_USER_MODEL = "users.User"
TEST_RUNNER = "core.test_runner.BackendOnlyDiscoverRunner"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": get_env("DRF_ANON_THROTTLE_RATE", "300/hour"),
        "user": get_env("DRF_USER_THROTTLE_RATE", "3000/hour"),
        "auth_token": get_env("DRF_AUTH_TOKEN_THROTTLE_RATE", "30/minute"),
        "registration": get_env("DRF_REGISTRATION_THROTTLE_RATE", "20/hour"),
        "setup_otp": get_env("DRF_SETUP_OTP_THROTTLE_RATE", "30/hour"),
        "public_estimate": get_env("DRF_PUBLIC_ESTIMATE_THROTTLE_RATE", "120/hour"),
        "public_estimate_action": get_env("DRF_PUBLIC_ESTIMATE_ACTION_THROTTLE_RATE", "20/hour"),
        "public_campaign": get_env("DRF_PUBLIC_CAMPAIGN_THROTTLE_RATE", "240/hour"),
        "public_issue_report": get_env("DRF_PUBLIC_ISSUE_REPORT_THROTTLE_RATE", "60/hour"),
        "uploads": get_env("DRF_UPLOAD_THROTTLE_RATE", "120/hour"),
    },
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
