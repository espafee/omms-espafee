from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import RoleBasedPermission
from core.roles import ALL_ROLES, ADMIN, CLIENT, FINANCE
from core.viewsets import ServiceModelViewSet
from apps.tenants.services import get_user_tenant, is_platform_super_admin

from .serializers import (
    CampaignEstimateLineSerializer,
    CampaignEstimateSerializer,
    ClientStatementSerializer,
    CreditNoteSerializer,
    GenerateInvoiceFromBookingsSerializer,
    InvoiceCancelSerializer,
    InvoiceEventSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    InvoicePaymentCreateSerializer,
    InvoiceSequenceSerializer,
    InvoiceSummarySerializer,
    PaymentSerializer,
    PublicCampaignEstimateSerializer,
    PublicEstimateDecisionSerializer,
    SupplierProfileSerializer,
)
from .permissions import enforce_finance_permission
from .services import (
    CampaignEstimateLineService,
    CampaignEstimateService,
    CreditNoteService,
    InvoiceLineService,
    InvoiceService,
    InvoiceEventService,
    PaymentService,
    PublicEstimateAccessError,
    SupplierProfileService,
    build_client_statement_csv,
    render_client_statement_pdf,
)

User = get_user_model()


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
    write_roles_by_action = {
        "issue": (ADMIN, FINANCE),
        "cancel": (ADMIN, FINANCE),
        "generate_pdf": (ADMIN, FINANCE),
        "generate_from_bookings": (ADMIN, FINANCE),
        "payments": (ADMIN, FINANCE),
    }
    filterset_fields = ["campaign", "status", "issue_date", "invoice_date", "due_date", "financial_year"]
    search_fields = ["invoice_number", "campaign__name", "campaign__code", "client_legal_name", "supplier_legal_name"]
    ordering_fields = ["issue_date", "invoice_date", "due_date", "total_amount", "grand_total", "created_at"]

    @extend_schema(responses=InvoiceSummarySerializer)
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        enforce_finance_permission(request.user, "view_finance_dashboard")
        summary = self.get_service().get_summary(user=request.user)
        return Response(InvoiceSummarySerializer(instance=summary).data)

    @extend_schema(request=GenerateInvoiceFromBookingsSerializer, responses=InvoiceSerializer)
    @action(detail=False, methods=["post"], url_path="generate-from-bookings")
    def generate_from_bookings(self, request):
        enforce_finance_permission(request.user, "issue_invoice")
        serializer = GenerateInvoiceFromBookingsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        invoice = self.get_service().generate_from_bookings(actor=request.user, **serializer.validated_data)
        return Response(self.get_serializer(instance=invoice).data)

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        enforce_finance_permission(request.user, "issue_invoice")
        invoice = self.get_object()
        issued_invoice = self.get_service().issue(invoice, actor=request.user)
        serializer = self.get_serializer(instance=issued_invoice)
        return Response(serializer.data)

    @extend_schema(request=InvoiceCancelSerializer, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        enforce_finance_permission(request.user, "void_invoice")
        invoice = self.get_object()
        serializer = InvoiceCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cancelled_invoice = self.get_service().cancel(
            invoice,
            actor=request.user,
            reason=serializer.validated_data["reason"],
            credit_amount=serializer.validated_data.get("credit_amount"),
            credit_date=serializer.validated_data.get("credit_date"),
            credit_method=serializer.validated_data.get("credit_method", ""),
            credit_reference_number=serializer.validated_data.get("credit_reference_number", ""),
            credit_notes=serializer.validated_data.get("credit_notes", ""),
        )
        return Response(self.get_serializer(instance=cancelled_invoice).data)

    def _resolve_statement_client(self, request):
        client_id = request.query_params.get("client")
        if not client_id:
            return None, Response({"client": ["Client query parameter is required."]}, status=400)
        try:
            queryset = User.objects.all()
            if not is_platform_super_admin(request.user):
                queryset = queryset.filter(tenant=get_user_tenant(request.user))
            client = queryset.get(pk=client_id)
        except User.DoesNotExist:
            return None, Response({"client": ["Client does not exist."]}, status=404)
        if getattr(request.user, "role", None) == CLIENT and client.pk != request.user.pk:
            return None, Response({"detail": "You can only access your own client statement."}, status=403)
        return client, None

    @extend_schema(responses=ClientStatementSerializer)
    @action(detail=False, methods=["get"], url_path="client-statement")
    def client_statement(self, request):
        enforce_finance_permission(request.user, "export_statement")
        client, error_response = self._resolve_statement_client(request)
        if error_response:
            return error_response
        statement = self.get_service().get_client_statement(client=client, user=request.user)
        return Response(ClientStatementSerializer(instance=statement).data)

    @extend_schema(responses=None)
    @action(detail=False, methods=["get"], url_path="client-statement/export-csv")
    def client_statement_csv(self, request):
        enforce_finance_permission(request.user, "export_statement")
        client, error_response = self._resolve_statement_client(request)
        if error_response:
            return error_response
        statement = self.get_service().get_client_statement(client=client, user=request.user)
        filename = f"client-statement-{client.pk}.csv"
        response = HttpResponse(build_client_statement_csv(statement), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @extend_schema(responses=None)
    @action(detail=False, methods=["get"], url_path="client-statement/export-pdf")
    def client_statement_pdf(self, request):
        enforce_finance_permission(request.user, "export_statement")
        client, error_response = self._resolve_statement_client(request)
        if error_response:
            return error_response
        statement = self.get_service().get_client_statement(client=client, user=request.user)
        filename = f"client-statement-{client.pk}.pdf"
        response = HttpResponse(render_client_statement_pdf(statement), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @extend_schema(request=None, responses=InvoiceSerializer)
    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        enforce_finance_permission(request.user, "issue_invoice")
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

    @extend_schema(request=None, responses=None)
    @action(detail=True, methods=["get"], url_path="download-pdf")
    def download_pdf(self, request, pk=None):
        invoice = self.get_object()
        pdf_bytes, filename = self.get_service().render_pdf_download(invoice, actor=request.user)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @extend_schema(request=InvoicePaymentCreateSerializer, responses=PaymentSerializer)
    @action(detail=True, methods=["post"], url_path="payments")
    def payments(self, request, pk=None):
        enforce_finance_permission(request.user, "record_payment")
        invoice = self.get_object()
        serializer = InvoicePaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = PaymentService().create(actor=request.user, invoice=invoice, **serializer.validated_data)
        return Response(PaymentSerializer(instance=payment).data, status=201)


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


class CreditNoteViewSet(ServiceModelViewSet):
    serializer_class = CreditNoteSerializer
    permission_classes = [RoleBasedPermission]
    service_class = CreditNoteService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    filterset_fields = ["invoice", "method", "credit_date"]
    search_fields = ["invoice__invoice_number", "reference_number", "reason", "notes"]
    ordering_fields = ["credit_date", "amount", "created_at"]


class InvoiceEventViewSet(ServiceModelViewSet):
    serializer_class = InvoiceEventSerializer
    permission_classes = [RoleBasedPermission]
    service_class = InvoiceEventService
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["invoice", "event_type", "actor", "invoice__campaign", "invoice__campaign__client"]
    search_fields = ["message", "invoice__invoice_number", "invoice__campaign__name", "invoice__client_legal_name"]
    ordering_fields = ["created_at", "event_type"]


class BillingSummaryView(APIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = ALL_ROLES
    write_roles = (ADMIN, FINANCE)

    def get(self, request, *args, **kwargs):
        enforce_finance_permission(request.user, "view_finance_dashboard")
        summary = InvoiceService().get_summary(user=request.user)
        return Response(
            {
                "total_estimated": summary["total_estimated"],
                "total_approved_estimates": summary["total_approved_estimates"],
                "total_invoiced": summary["total_invoiced"],
                "total_collected": summary["total_collected"],
                "outstanding_balance": summary["outstanding_balance"],
                "overdue_amount": summary["overdue_amount"],
            }
        )


class PublicEstimateDetailView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_estimate"

    @extend_schema(responses=PublicCampaignEstimateSerializer)
    def get(self, request, token, *args, **kwargs):
        service = CampaignEstimateService()
        try:
            estimate = service.resolve_public(token)
        except PublicEstimateAccessError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)
        return Response(PublicCampaignEstimateSerializer(instance=estimate).data)

class PublicEstimateApproveView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_estimate_action"

    @extend_schema(request=PublicEstimateDecisionSerializer, responses=PublicCampaignEstimateSerializer)
    def post(self, request, token, *args, **kwargs):
        serializer = PublicEstimateDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = CampaignEstimateService()
        try:
            estimate = service.respond_public(token, decision="approve", comment=serializer.validated_data.get("comment", ""))
        except PublicEstimateAccessError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)
        return Response(PublicCampaignEstimateSerializer(instance=estimate).data)


class PublicEstimateRejectView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "public_estimate_action"

    @extend_schema(request=PublicEstimateDecisionSerializer, responses=PublicCampaignEstimateSerializer)
    def post(self, request, token, *args, **kwargs):
        serializer = PublicEstimateDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = CampaignEstimateService()
        try:
            estimate = service.respond_public(token, decision="reject", comment=serializer.validated_data.get("comment", ""))
        except PublicEstimateAccessError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)
        return Response(PublicCampaignEstimateSerializer(instance=estimate).data)
