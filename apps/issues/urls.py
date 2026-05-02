from rest_framework.routers import DefaultRouter

from .views import IssueViewSet

router = DefaultRouter()
router.register("", IssueViewSet, basename="issues")

urlpatterns = router.urls
