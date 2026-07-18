from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthHealthView,
    ClientDirectoryView,
    CustomTokenRefreshView,
    CustomTokenVerifyView,
    CurrentUserView,
    CustomTokenObtainPairView,
    FieldStaffDirectoryView,
    LogoutView,
    RegisterView,
    UserViewSet,
)

router = DefaultRouter()
router.register("", UserViewSet, basename="users")

urlpatterns = [
    path("clients/", ClientDirectoryView.as_view(), name="client-directory"),
    path("field-staff/", FieldStaffDirectoryView.as_view(), name="field-staff-directory"),
    path("auth/register/", RegisterView.as_view(), name="users-register"),
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="auth-login"),
    path("auth/token/", CustomTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", CustomTokenVerifyView.as_view(), name="token-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user"),
    path("auth/health/", AuthHealthView.as_view(), name="auth-health"),
]

urlpatterns += router.urls
