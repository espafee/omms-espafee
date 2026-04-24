from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CampaignAccessTokenViewSet, CampaignAssetViewSet, CampaignViewSet, PublicCampaignAccessView

router = DefaultRouter()
router.register("assets", CampaignAssetViewSet, basename="campaign-assets")
router.register("access-links", CampaignAccessTokenViewSet, basename="campaign-access-links")
router.register("", CampaignViewSet, basename="campaigns")

urlpatterns = [
    path("public/<str:token>/", PublicCampaignAccessView.as_view(), name="campaigns-public-detail"),
]
urlpatterns += router.urls
