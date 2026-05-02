from rest_framework.routers import DefaultRouter

from .views import IssueTaskViewSet

router = DefaultRouter()
router.register("", IssueTaskViewSet, basename="issue-tasks")

urlpatterns = router.urls
