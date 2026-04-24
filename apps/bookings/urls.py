from rest_framework.routers import DefaultRouter

from .views import BookingViewSet

router = DefaultRouter()
router.register("", BookingViewSet, basename="bookings")

urlpatterns = router.urls
