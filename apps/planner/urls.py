from rest_framework.routers import DefaultRouter

from .views import CampaignProposalViewSet, MediaPlannerShareLinkViewSet

router = DefaultRouter()
router.register("links", MediaPlannerShareLinkViewSet, basename="planner-links")
router.register("proposals", CampaignProposalViewSet, basename="planner-proposals")

urlpatterns = router.urls
