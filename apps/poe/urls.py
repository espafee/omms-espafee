from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FieldPoeLinkCreateView,
    ProofOfExecutionMediaViewSet,
    ProofOfExecutionVerifyView,
    ProofOfExecutionViewSet,
    PublicFieldPoeUploadView,
)

router = DefaultRouter()
router.register("media", ProofOfExecutionMediaViewSet, basename="poe-media")
router.register("", ProofOfExecutionViewSet, basename="poe")

urlpatterns = [
    path("verify/", ProofOfExecutionVerifyView.as_view(), name="poe-verify"),
    path("field-upload-links/", FieldPoeLinkCreateView.as_view(), name="poe-field-upload-link-create"),
    path("field-upload/<str:token>/", PublicFieldPoeUploadView.as_view(), name="poe-field-upload"),
    *router.urls,
]
