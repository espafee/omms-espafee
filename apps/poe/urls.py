from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ProofOfExecutionMediaViewSet, ProofOfExecutionVerifyView, ProofOfExecutionViewSet

router = DefaultRouter()
router.register("media", ProofOfExecutionMediaViewSet, basename="poe-media")
router.register("", ProofOfExecutionViewSet, basename="poe")

urlpatterns = [
    path("verify/", ProofOfExecutionVerifyView.as_view(), name="poe-verify"),
    *router.urls,
]
