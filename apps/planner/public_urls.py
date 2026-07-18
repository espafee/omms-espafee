from django.urls import path

from .views import PublicMediaPlannerView, PublicMediaProposalSubmitView

urlpatterns = [
    path("<str:token>/", PublicMediaPlannerView.as_view(), name="public-media-planner"),
    path("<str:token>/proposals/", PublicMediaProposalSubmitView.as_view(), name="public-media-proposal-submit"),
]
