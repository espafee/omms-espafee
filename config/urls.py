from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.billing.views import PublicEstimateApproveView, PublicEstimateDetailView, PublicEstimateRejectView
from apps.issues.views import PublicIssueReportView
from apps.observability.views import HealthView
from core.images import is_local_media_storage_backend

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="redoc"),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/team/", include("apps.users.team_urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/bookings/", include("apps.bookings.urls")),
    path("api/v1/campaigns/", include("apps.campaigns.urls")),
    path("api/v1/poe/", include("apps.poe.urls")),
    path("api/v1/issues/", include("apps.issues.urls")),
    path("api/v1/tasks/", include("apps.issues.task_urls")),
    path("api/v1/public/issue-report/<str:token>/", PublicIssueReportView.as_view(), name="public-issue-report"),
    path("api/v1/public/estimates/<str:token>/", PublicEstimateDetailView.as_view(), name="public-estimate-detail"),
    path("api/v1/public/estimates/<str:token>/approve/", PublicEstimateApproveView.as_view(), name="public-estimate-approve"),
    path("api/v1/public/estimates/<str:token>/reject/", PublicEstimateRejectView.as_view(), name="public-estimate-reject"),
    path("public/issue-report/<str:token>/", PublicIssueReportView.as_view(), name="public-issue-report-legacy"),
    path("api/v1/billing/", include("apps.billing.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/observability/", include("apps.observability.urls")),
    path("api/v1/setup/", include("apps.setup.urls")),
    path("api/v1/training/", include("apps.training.urls")),
    path("api/v1/mobile/", include("apps.mobile.urls")),
    path("api/v1/planner/", include("apps.planner.urls")),
    path("api/v1/public/media-planner/", include("apps.planner.public_urls")),
]

if settings.DEBUG or is_local_media_storage_backend(settings.STORAGES["default"]["BACKEND"]):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
