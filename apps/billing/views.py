from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, FINANCE
from core.viewsets import ServiceModelViewSet

from .serializers import InvoiceLineSerializer, InvoiceSerializer, InvoiceSummarySerializer, PaymentSerializer
from .services import InvoiceLineService, InvoiceService, PaymentService


class InvoiceViewSet(ServiceModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [RoleBasedPermission]
    service_class = InvoiceService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["campaign", "status", "issue_date", "due_date"]
    search_fields = ["invoice_number", "campaign__name", "campaign__code"]
    ordering_fields = ["issue_date", "due_date", "total_amount", "created_at"]

    @extend_schema(responses=InvoiceSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        summary = self.get_service().get_summary(user=request.user)
        return Response(InvoiceSummarySerializer(instance=summary).data)


class InvoiceLineViewSet(ServiceModelViewSet):
    serializer_class = InvoiceLineSerializer
    permission_classes = [RoleBasedPermission]
    service_class = InvoiceLineService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["invoice", "booking"]
    search_fields = ["description", "invoice__invoice_number"]
    ordering_fields = ["created_at", "line_total"]


class PaymentViewSet(ServiceModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [RoleBasedPermission]
    service_class = PaymentService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["invoice", "method", "payment_date"]
    search_fields = ["invoice__invoice_number", "reference_number"]
    ordering_fields = ["payment_date", "amount", "created_at"]
