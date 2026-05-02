from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.issues.views import PublicIssueReportView
from core.images import is_local_media_storage_backend

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="redoc"),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/bookings/", include("apps.bookings.urls")),
    path("api/v1/campaigns/", include("apps.campaigns.urls")),
    path("api/v1/poe/", include("apps.poe.urls")),
    path("api/v1/issues/", include("apps.issues.urls")),
    path("api/v1/tasks/", include("apps.issues.task_urls")),
    path("api/v1/public/issue-report/<str:token>/", PublicIssueReportView.as_view(), name="public-issue-report"),
    path("public/issue-report/<str:token>/", PublicIssueReportView.as_view(), name="public-issue-report-legacy"),
    path("api/v1/billing/", include("apps.billing.urls")),
    path("api/v1/setup/", include("apps.setup.urls")),
    path("api/v1/mobile/", include("apps.mobile.urls")),
]

if settings.DEBUG or is_local_media_storage_backend(settings.STORAGES["default"]["BACKEND"]):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
