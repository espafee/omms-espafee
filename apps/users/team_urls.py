from django.urls import path
from rest_framework.routers import DefaultRouter

from .team_views import PasswordSetupCompleteView, TeamRolesView, TeamUserViewSet

router = DefaultRouter()
router.register("users", TeamUserViewSet, basename="team-users")

urlpatterns = [
    path("roles/", TeamRolesView.as_view(), name="team-roles"),
    path("account-setup/complete/", PasswordSetupCompleteView.as_view(), name="team-account-setup-complete"),
]
urlpatterns += router.urls
