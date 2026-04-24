from rest_framework.routers import DefaultRouter

from .views import (
    MediaSiteImageViewSet,
    MediaSiteViewSet,
    MediaUnitImageViewSet,
    MediaUnitViewSet,
    RateCardViewSet,
)

router = DefaultRouter()
router.register("sites", MediaSiteViewSet, basename="inventory-sites")
router.register("site-images", MediaSiteImageViewSet, basename="inventory-site-images")
router.register("units", MediaUnitViewSet, basename="inventory-units")
router.register("unit-images", MediaUnitImageViewSet, basename="inventory-unit-images")
router.register("rate-cards", RateCardViewSet, basename="inventory-ratecards")

urlpatterns = router.urls
