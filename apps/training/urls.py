from django.urls import path

from apps.training.views import TrainingDocumentDownloadView, TrainingDocumentListView

urlpatterns = [
    path("documents/", TrainingDocumentListView.as_view(), name="training-document-list"),
    path("documents/<slug:slug>/download/", TrainingDocumentDownloadView.as_view(), name="training-document-download"),
]
