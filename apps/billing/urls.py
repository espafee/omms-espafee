from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BillingSummaryView,
    CampaignEstimateLineViewSet,
    CampaignEstimateViewSet,
    CreditNoteViewSet,
    InvoiceEventViewSet,
    InvoiceLineViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    SupplierProfileViewSet,
)

router = DefaultRouter()
router.register("supplier-profiles", SupplierProfileViewSet, basename="billing-supplier-profiles")
router.register("campaign-estimates", CampaignEstimateViewSet, basename="billing-campaign-estimates")
router.register("campaign-estimate-lines", CampaignEstimateLineViewSet, basename="billing-campaign-estimate-lines")
router.register("invoices", InvoiceViewSet, basename="billing-invoices")
router.register("invoice-lines", InvoiceLineViewSet, basename="billing-invoice-lines")
router.register("payments", PaymentViewSet, basename="billing-payments")
router.register("credit-notes", CreditNoteViewSet, basename="billing-credit-notes")
router.register("invoice-events", InvoiceEventViewSet, basename="billing-invoice-events")

urlpatterns = [
    path("summary/", BillingSummaryView.as_view(), name="billing-summary"),
]
urlpatterns += router.urls
