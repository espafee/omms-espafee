from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, FINANCE
from core.viewsets import ServiceModelViewSet

from .serializers import (
    CampaignEstimateLineSerializer,
    CampaignEstimateSerializer,
    GenerateInvoiceFromBookingsSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    InvoiceSequenceSerializer,
    InvoiceSummarySerializer,
    PaymentSerializer,
    PublicCampaignEstimateSerializer,
    PublicEstimateDecisionSerializer,
    SupplierProfileSerializer,
)
from .services import (
    CampaignEstimateLineService,
    CampaignEstimateService,
    InvoiceLineService,
    InvoiceService,
    PaymentService,
    PublicEstimateAccessError,
    SupplierProfileService,
)


class SupplierProfileViewSet(ServiceModelViewSet):
    serializer_class = SupplierProfileSerializer
    permission_classes = [RoleBasedPermission]
    service_class = SupplierProfileService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["is_active", "state", "state_code"]
    search_fields = ["legal_name", "trade_name", "gstin", "city"]
    ordering_fields = ["legal_name", "created_at"]


class CampaignEstimateViewSet(ServiceModelViewSet):
    serializer_class = CampaignEstimateSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignEstimateService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    write_roles_by_action = {"share": (ADMIN, FINANCE), "approve": (ADMIN, FINANCE), "reject": (ADMIN, FINANCE), "finalize": (ADMIN, FINANCE)}
    filterset_fields = ["client", "campaign", "status"]
    search_fields = ["estimate_number", "title", "client__email", "client__organization_name", "campaign__name"]
    ordering_fields = ["start_date", "end_date", "total_amount", "created_at"]

    @extend_schema(request=None, responses=CampaignEstimateSerializer)
    @action(detail=True, methods=["post"], url_path="share")
    def share(self, request, pk=None):
        estimate = self.get_object()
        updated = self.get_service().share(estimate, actor=request.user)
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=None, responses=CampaignEstimateSerializer)
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        estimate = self.get_object()
        updated = self.get_service().approve(estimate, actor=request.user)
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=None, responses=CampaignEstimateSerializer)
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        estimate = self.get_object()
        updated = self.get_service().reject(estimate, actor=request.user)
        return Response(self.get_serializer(updated).data)

    @extend_schema(request=None, responses=CampaignEstimateSerializer)
    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        estimate = self.get_object()
        updated = self.get_service().approve(estimate, actor=request.user)
        return Response(self.get_serializer(updated).data)


class CampaignEstimateLineViewSet(ServiceModelViewSet):
    serializer_class = CampaignEstimateLineSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CampaignEstimateLineService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["estimate", "media_unit"]
    search_fields = ["description", "estimate__estimate_number", "media_unit__unit_code"]
    ordering_fields = ["start_date", "end_date", "total_amount", "created_at"]


class InvoiceViewSet(ServiceModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [RoleBasedPermission]
    service_class = InvoiceService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    write_roles_by_action = {"issue": (ADMIN, FINANCE), "generate_pdf": (ADMIN, FINANCE), "generate_from_bookings": (ADMIN, FINANCE)}
    filterset_fields = ["campaign", "status", "issue_date", "invoice_date", "due_date", "financial_year"]
    search_fields = ["invoice_number", "campaign__name", "campaign__code", "client_legal_name", "supplier_legal_name"]
    ordering_fields = ["issue_date", "invoice_date", "due_date", "total_amount", "grand_total", "created_at"]

    @extend_schema(responses=InvoiceSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        summary = self.get_service().get_summary(user=request.user)
        return Response(InvoiceSummarySerializer(instance=summary).data)

    @extend_schema(request=GenerateInvoiceFromBookingsSerializer, responses=InvoiceSerializer)
    @action(detail=False, methods=["post"], url_path="generate-from-bookings")
    def generate_from_bookings(self, request):
        serializer = GenerateInvoiceFromBookingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = self.get_service().generate_from_bookings(actor=request.user, **serializer.validated_data)
        return Response(self.get_serializer(instance=invoice).data)

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


class PublicEstimateApprovalView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=PublicCampaignEstimateSerializer)
    def get(self, request, token, *args, **kwargs):
        service = CampaignEstimateService()
        try:
            estimate = service.resolve_public(token)
        except PublicEstimateAccessError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)
        return Response(PublicCampaignEstimateSerializer(instance=estimate).data)

    @extend_schema(request=PublicEstimateDecisionSerializer, responses=PublicCampaignEstimateSerializer)
    def post(self, request, token, *args, **kwargs):
        serializer = PublicEstimateDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = CampaignEstimateService()
        try:
            estimate = service.respond_public(token, decision=serializer.validated_data["decision"])
        except PublicEstimateAccessError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)
        return Response(PublicCampaignEstimateSerializer(instance=estimate).data)
