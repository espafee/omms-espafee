from rest_framework.routers import DefaultRouter

from .views import InvoiceLineViewSet, InvoiceViewSet, PaymentViewSet, SupplierProfileViewSet

router = DefaultRouter()
router.register("supplier-profiles", SupplierProfileViewSet, basename="billing-supplier-profiles")
router.register("invoices", InvoiceViewSet, basename="billing-invoices")
router.register("invoice-lines", InvoiceLineViewSet, basename="billing-invoice-lines")
router.register("payments", PaymentViewSet, basename="billing-payments")

urlpatterns = router.urls
