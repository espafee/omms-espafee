from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CampaignEstimateLineViewSet,
    CampaignEstimateViewSet,
    InvoiceLineViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    PublicEstimateApprovalView,
    SupplierProfileViewSet,
)

router = DefaultRouter()
router.register("supplier-profiles", SupplierProfileViewSet, basename="billing-supplier-profiles")
router.register("campaign-estimates", CampaignEstimateViewSet, basename="billing-campaign-estimates")
router.register("campaign-estimate-lines", CampaignEstimateLineViewSet, basename="billing-campaign-estimate-lines")
router.register("invoices", InvoiceViewSet, basename="billing-invoices")
router.register("invoice-lines", InvoiceLineViewSet, basename="billing-invoice-lines")
router.register("payments", PaymentViewSet, basename="billing-payments")

urlpatterns = [
    path("public/estimate/<str:token>/", PublicEstimateApprovalView.as_view(), name="billing-public-estimate-detail"),
]
urlpatterns += router.urls
