from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, FINANCE
from core.viewsets import ServiceModelViewSet

from .serializers import (
    InvoiceLineSerializer,
    InvoiceSerializer,
    InvoiceSequenceSerializer,
    InvoiceSummarySerializer,
    PaymentSerializer,
    SupplierProfileSerializer,
)
from .services import InvoiceLineService, InvoiceService, PaymentService, SupplierProfileService


class SupplierProfileViewSet(ServiceModelViewSet):
    serializer_class = SupplierProfileSerializer
    permission_classes = [RoleBasedPermission]
    service_class = SupplierProfileService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["is_active", "state", "state_code"]
    search_fields = ["legal_name", "trade_name", "gstin", "city"]
    ordering_fields = ["legal_name", "created_at"]


class InvoiceViewSet(ServiceModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [RoleBasedPermission]
    service_class = InvoiceService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    write_roles_by_action = {"issue": (ADMIN, FINANCE), "generate_pdf": (ADMIN, FINANCE)}
    filterset_fields = ["campaign", "status", "issue_date", "invoice_date", "due_date", "financial_year"]
    search_fields = ["invoice_number", "campaign__name", "campaign__code", "client_legal_name", "supplier_legal_name"]
    ordering_fields = ["issue_date", "invoice_date", "due_date", "total_amount", "grand_total", "created_at"]

    @extend_schema(responses=InvoiceSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        summary = self.get_service().get_summary(user=request.user)
        return Response(InvoiceSummarySerializer(instance=summary).data)

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        invoice = self.get_object()
        issued_invoice = self.get_service().issue(invoice, actor=request.user)
        serializer = self.get_serializer(instance=issued_invoice)
        return Response(serializer.data)

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        invoice = self.get_object()
        updated_invoice = self.get_service().generate_pdf(invoice, actor=request.user)
        serializer = self.get_serializer(instance=updated_invoice)
        return Response(serializer.data)

    @extend_schema(request=None, responses=None)
    @action(detail=True, methods=["get"], url_path="pdf-link")
    def pdf_link(self, request, pk=None):
        invoice = self.get_object()
        signed_url = self.get_service().get_pdf_link(invoice)
        return Response(
            {
                "url": signed_url,
                "expires_in": getattr(settings, "AWS_PRIVATE_SIGNED_URL_EXPIRY_SECONDS", 900),
            }
        )


class InvoiceLineViewSet(ServiceModelViewSet):
    serializer_class = InvoiceLineSerializer
    permission_classes = [RoleBasedPermission]
    service_class = InvoiceLineService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["invoice", "booking", "sac_code", "hsn_code"]
    search_fields = ["description", "item_description", "invoice__invoice_number"]
    ordering_fields = ["line_number", "created_at", "line_total"]


class PaymentViewSet(ServiceModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [RoleBasedPermission]
    service_class = PaymentService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["invoice", "method", "payment_date"]
    search_fields = ["invoice__invoice_number", "reference_number"]
    ordering_fields = ["payment_date", "amount", "created_at"]
