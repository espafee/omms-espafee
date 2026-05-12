from rest_framework.routers import DefaultRouter

from .views import EmailNotificationLogViewSet, NotificationPreferenceViewSet

router = DefaultRouter()
router.register("logs", EmailNotificationLogViewSet, basename="notification-logs")
router.register("preferences", NotificationPreferenceViewSet, basename="notification-preferences")

urlpatterns = router.urls
