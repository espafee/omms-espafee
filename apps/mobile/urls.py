from django.urls import path

from .views import AssignedWorkView, MobilePoeSubmitView

urlpatterns = [
    path("assigned-work/", AssignedWorkView.as_view(), name="mobile-assigned-work"),
    path("poe/submit/", MobilePoeSubmitView.as_view(), name="mobile-poe-submit"),
]
