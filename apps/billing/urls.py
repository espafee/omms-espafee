from rest_framework.routers import DefaultRouter

from .views import InvoiceLineViewSet, InvoiceViewSet, PaymentViewSet

router = DefaultRouter()
router.register("invoices", InvoiceViewSet, basename="billing-invoices")
router.register("invoice-lines", InvoiceLineViewSet, basename="billing-invoice-lines")
router.register("payments", PaymentViewSet, basename="billing-payments")

urlpatterns = router.urls
