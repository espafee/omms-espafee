from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import CampaignEstimate, CampaignEstimateLine, Invoice, InvoiceLine, InvoiceSequence, Payment, SupplierProfile
from apps.billing.services import CampaignEstimateService, generate_invoice_pdf, get_indian_financial_year, issue_invoice
from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit

from .storage_backends import MemoryPrivateDocumentStorage

User = get_user_model()


class BillingServiceTests(TestCase):
    def setUp(self):
        MemoryPrivateDocumentStorage.reset()
        self.password = "TestPass123!"
        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.finance = self._create_user("finance@example.com", "finance_user", User.Role.FINANCE)
        self.client_user = self._create_user("client@example.com", "client_user", User.Role.CLIENT)
        self.sales = self._create_user("sales@example.com", "sales_user", User.Role.SALES)

        self.site = MediaSite.objects.create(
            name="Billing Site",
            code="SITE-BILL-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Main Road",
            city="Jammu",
            state="Jammu and Kashmir",
            owner=self.admin,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-BILL-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=True,
            monthly_rate=Decimal("50000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="GST Campaign",
            code="CMP-GST-001",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            budget=Decimal("250000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Billing compliance",
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )
        self.supplier = SupplierProfile.objects.create(
            legal_name="OMMS Media Private Limited",
            trade_name="OMMS Media",
            gstin="01ABCDE1234F1Z5",
            address_line_1="123 Business Park",
            city="Jammu",
            state="Jammu and Kashmir",
            postal_code="180001",
            state_code="01",
            contact_email="accounts@omms.test",
            contact_phone="9999999999",
            bank_details="A/c Holder: OMMS Media Private Limited\nBank Name & Branch: Demo Bank, Jammu\nA/c No.: 1234567890\nIFSC: DEMO0001234",
        )

    def _create_user(self, email, username, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
        )

    def _build_invoice(self, *, place_of_supply_state_code="01", invoice_date=date(2025, 4, 15)):
        invoice = Invoice.objects.create(
            campaign=self.campaign,
            supplier_profile=self.supplier,
            invoice_date=invoice_date,
            due_date=invoice_date + timedelta(days=15),
            client_legal_name="Client Outdoor Limited",
            client_gstin="01AAACC1234D1Z6",
            client_billing_address_line_1="Corporate Avenue",
            client_billing_city="Jammu",
            client_billing_state="Jammu and Kashmir",
            client_billing_postal_code="180004",
            client_billing_state_code=place_of_supply_state_code,
            place_of_supply_state="Jammu and Kashmir" if place_of_supply_state_code == "01" else "Punjab",
            place_of_supply_state_code=place_of_supply_state_code,
            payment_terms="Net 15",
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            booking=self.booking,
            description="Billboard display service",
            sac_code="998361",
            quantity=Decimal("2.00"),
            unit_price=Decimal("100.00"),
            discount_amount=Decimal("10.00"),
            gst_rate=Decimal("18.00"),
        )
        return invoice

    def test_indian_financial_year_calculation(self):
        self.assertEqual(get_indian_financial_year(date(2025, 4, 1)), "2025-26")
        self.assertEqual(get_indian_financial_year(date(2026, 3, 31)), "2025-26")
        self.assertEqual(get_indian_financial_year(date(2025, 1, 1)), "2024-25")

    def test_issue_invoice_allocates_number_and_calculates_intrastate_tax(self):
        invoice = self._build_invoice(place_of_supply_state_code="01")

        issued = issue_invoice(invoice, self.finance)
        line = issued.lines.get()

        self.assertEqual(issued.invoice_number, "INV/2025-26/0001")
        self.assertEqual(issued.financial_year, "2025-26")
        self.assertEqual(issued.status, Invoice.Status.ISSUED)
        self.assertEqual(issued.issued_by, self.finance)
        self.assertIsNotNone(issued.issued_at)
        self.assertEqual(issued.taxable_value_total, Decimal("190.00"))
        self.assertEqual(issued.discount_total, Decimal("10.00"))
        self.assertEqual(issued.cgst_total, Decimal("17.10"))
        self.assertEqual(issued.sgst_total, Decimal("17.10"))
        self.assertEqual(issued.igst_total, Decimal("0.00"))
        self.assertEqual(issued.total_tax, Decimal("34.20"))
        self.assertEqual(issued.grand_total, Decimal("224.20"))
        self.assertEqual(issued.issue_date, issued.invoice_date)
        self.assertEqual(line.gross_value, Decimal("200.00"))
        self.assertEqual(line.taxable_value, Decimal("190.00"))
        self.assertEqual(line.cgst_rate, Decimal("9.00"))
        self.assertEqual(line.sgst_rate, Decimal("9.00"))
        self.assertEqual(line.igst_rate, Decimal("0.00"))
        self.assertEqual(line.line_total, Decimal("224.20"))

    def test_issue_invoice_calculates_interstate_igst(self):
        invoice = self._build_invoice(place_of_supply_state_code="03")

        issued = issue_invoice(invoice, self.finance)
        line = issued.lines.get()

        self.assertEqual(issued.cgst_total, Decimal("0.00"))
        self.assertEqual(issued.sgst_total, Decimal("0.00"))
        self.assertEqual(issued.igst_total, Decimal("34.20"))
        self.assertEqual(line.igst_rate, Decimal("18.00"))
        self.assertEqual(line.igst_amount, Decimal("34.20"))

    def test_invoice_number_allocation_does_not_duplicate(self):
        first = issue_invoice(self._build_invoice(invoice_date=date(2025, 4, 15)), self.finance)
        second = issue_invoice(self._build_invoice(invoice_date=date(2025, 5, 15)), self.finance)

        self.assertEqual(first.invoice_number, "INV/2025-26/0001")
        self.assertEqual(second.invoice_number, "INV/2025-26/0002")

    def test_invoice_number_allocation_skips_existing_numbers_without_sequence(self):
        Invoice.objects.create(
            campaign=self.campaign,
            invoice_number="INV/2025-26/0001",
            financial_year="2025-26",
            status=Invoice.Status.CANCELLED,
        )

        issued = issue_invoice(self._build_invoice(invoice_date=date(2025, 4, 15)), self.finance)

        self.assertEqual(issued.invoice_number, "INV/2025-26/0002")
        sequence = InvoiceSequence.objects.get(
            document_type=InvoiceSequence.DocumentType.INVOICE,
            financial_year="2025-26",
        )
        self.assertEqual(sequence.last_number, 2)

    def test_issue_overrides_manual_draft_invoice_number(self):
        invoice = self._build_invoice(invoice_date=date(2025, 4, 15))
        invoice.invoice_number = "MANUAL-DRAFT-001"
        invoice.save(update_fields=["invoice_number", "updated_at"])

        issued = issue_invoice(invoice, self.finance)

        self.assertEqual(issued.invoice_number, "INV/2025-26/0001")

    def test_cancelled_invoice_keeps_number_and_next_issue_moves_forward(self):
        first = issue_invoice(self._build_invoice(invoice_date=date(2025, 4, 15)), self.finance)
        first.status = Invoice.Status.CANCELLED
        first.cancellation_reason = "Client requested cancellation"
        first.cancelled_by = self.finance
        first.cancelled_at = first.issued_at
        first.save(update_fields=["status", "cancellation_reason", "cancelled_by", "cancelled_at", "updated_at"])

        second = issue_invoice(self._build_invoice(invoice_date=date(2025, 5, 1)), self.finance)

        self.assertEqual(first.invoice_number, "INV/2025-26/0001")
        self.assertEqual(second.invoice_number, "INV/2025-26/0002")

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    def test_generate_pdf_works_for_issued_invoice_and_uses_supplier_snapshot(self):
        issued = issue_invoice(self._build_invoice(place_of_supply_state_code="01"), self.finance)

        generated = generate_invoice_pdf(issued, actor=self.finance)

        self.assertEqual(generated.pdf_file.name, "invoices/2025-26/INV_2025-26_0001.pdf")
        self.assertIn(generated.pdf_file.name, MemoryPrivateDocumentStorage.saved_files)
        pdf_bytes = MemoryPrivateDocumentStorage.saved_files[generated.pdf_file.name]
        extracted_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)
        self.assertIn("OMMS Media Private Limited", extracted_text)
        self.assertIn("01ABCDE1234F1Z5", extracted_text)
        self.assertNotIn("ESPA FEE Pvt Ltd", extracted_text)

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    def test_generate_pdf_escapes_xml_sensitive_business_text(self):
        invoice = self._build_invoice(place_of_supply_state_code="01")
        invoice.supplier_profile.trade_name = "OMMS & Partners <North>"
        invoice.supplier_profile.bank_details = "A/c Holder: OMMS & Partners\nBank & Branch: Demo <Main>"
        invoice.supplier_profile.save(update_fields=["trade_name", "bank_details", "updated_at"])
        invoice.client_legal_name = "Client & Co <North>"
        invoice.client_billing_address_line_1 = "A & B Tower <Level 2>"
        invoice.campaign.name = "Admission & Launch <May>"
        invoice.campaign.save(update_fields=["name", "updated_at"])
        invoice.save(update_fields=["client_legal_name", "client_billing_address_line_1", "updated_at"])
        line = invoice.lines.get()
        line.description = "Flex & Installation <Premium>"
        line.item_description = "Flex & Installation <Premium>"
        line.unit_of_measure = "sqft & display"
        line.save(update_fields=["description", "item_description", "unit_of_measure", "updated_at"])

        issued = issue_invoice(invoice, self.finance)
        generated = generate_invoice_pdf(issued, actor=self.finance)

        pdf_bytes = MemoryPrivateDocumentStorage.saved_files[generated.pdf_file.name]
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    @patch("apps.billing.services.logger.exception")
    @patch("apps.billing.services.render_invoice_pdf", side_effect=RuntimeError("renderer failed"))
    def test_generate_pdf_falls_back_when_primary_renderer_errors(self, _render_invoice_pdf, _logger_exception):
        issued = issue_invoice(self._build_invoice(place_of_supply_state_code="01"), self.finance)

        generated = generate_invoice_pdf(issued, actor=self.finance)

        pdf_bytes = MemoryPrivateDocumentStorage.saved_files[generated.pdf_file.name]
        extracted_text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf_bytes)).pages)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertIn("Tax Invoice", extracted_text)
        self.assertIn(issued.invoice_number, extracted_text)

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    def test_draft_invoice_cannot_generate_official_pdf(self):
        invoice = self._build_invoice(place_of_supply_state_code="01")

        with self.assertRaisesMessage(Exception, "Only issued invoices can generate an official PDF."):
            generate_invoice_pdf(invoice, actor=self.finance)


class BillingApiTests(APITestCase):
    def setUp(self):
        MemoryPrivateDocumentStorage.reset()
        self.password = "TestPass123!"
        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.finance = self._create_user("finance@example.com", "finance_user", User.Role.FINANCE)
        self.client_user = self._create_user("client@example.com", "client_user", User.Role.CLIENT)
        self.sales = self._create_user("sales@example.com", "sales_user", User.Role.SALES)

        self.site = MediaSite.objects.create(
            name="Billing Site",
            code="SITE-BILL-API",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Main Road",
            city="Jammu",
            state="Jammu and Kashmir",
            owner=self.admin,
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="UNIT-BILL-API",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=True,
            monthly_rate=Decimal("50000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="GST API Campaign",
            code="CMP-GST-API",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            budget=Decimal("250000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Billing API compliance",
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )
        self.supplier = SupplierProfile.objects.create(
            legal_name="OMMS Media Private Limited",
            trade_name="OMMS Media",
            gstin="01ABCDE1234F1Z5",
            address_line_1="123 Business Park",
            city="Jammu",
            state="Jammu and Kashmir",
            postal_code="180001",
            state_code="01",
            bank_details="A/c Holder: OMMS Media Private Limited\nBank Name & Branch: Demo Bank, Jammu\nA/c No.: 1234567890\nIFSC: DEMO0001234",
        )

    def _create_user(self, email, username, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
        )

    def _create_draft_invoice(self):
        invoice = Invoice.objects.create(
            campaign=self.campaign,
            supplier_profile=self.supplier,
            invoice_date=date(2025, 4, 15),
            due_date=date(2025, 4, 30),
            client_legal_name="Client Outdoor Limited",
            client_gstin="01AAACC1234D1Z6",
            client_billing_address_line_1="Corporate Avenue",
            client_billing_city="Jammu",
            client_billing_state="Jammu and Kashmir",
            client_billing_postal_code="180004",
            client_billing_state_code="01",
            place_of_supply_state="Jammu and Kashmir",
            place_of_supply_state_code="01",
            payment_terms="Net 15",
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            booking=self.booking,
            description="Billboard display service",
            sac_code="998361",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            gst_rate=Decimal("18.00"),
        )
        return invoice

    def _create_estimate(self, *, status=CampaignEstimate.Status.DRAFT):
        estimate = CampaignEstimate.objects.create(
            client=self.client_user,
            campaign=self.campaign,
            title="April visibility plan",
            start_date=self.campaign.start_date,
            end_date=self.campaign.end_date,
            status=status,
            notes="Shared with client for approval.",
            created_by=self.finance,
        )
        CampaignEstimateLine.objects.create(
            estimate=estimate,
            media_unit=self.unit,
            description="Outdoor media display",
            start_date=self.campaign.start_date,
            end_date=self.campaign.end_date,
            quantity=Decimal("1.00"),
            unit_rate=Decimal("50000.00"),
            tax_rate=Decimal("18.00"),
            taxable_amount=Decimal("50000.00"),
            tax_amount=Decimal("9000.00"),
            total_amount=Decimal("59000.00"),
        )
        estimate.subtotal = Decimal("50000.00")
        estimate.tax_amount = Decimal("9000.00")
        estimate.total_amount = Decimal("59000.00")
        estimate.save(update_fields=["subtotal", "tax_amount", "total_amount", "updated_at"])
        return estimate

    def test_issue_endpoint_issues_invoice(self):
        invoice = self._create_draft_invoice()
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(reverse("billing-invoices-issue", args=[invoice.id]), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertEqual(invoice.invoice_number, "INV/2025-26/0001")
        self.assertEqual(response.data["invoice_number"], "INV/2025-26/0001")

    def test_issued_invoice_cannot_be_casually_edited(self):
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        self.client.force_authenticate(user=self.finance)

        response = self.client.patch(
            reverse("billing-invoices-detail", args=[invoice.id]),
            {"payment_terms": "Net 30"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    def test_existing_invoice_and_payment_summary_still_works(self):
        estimate = self._create_estimate(status=CampaignEstimate.Status.APPROVED)
        issued = issue_invoice(self._create_draft_invoice(), self.finance)
        issued.due_date = date.today() + timedelta(days=10)
        issued.save(update_fields=["due_date", "updated_at"])
        overdue = issue_invoice(self._create_draft_invoice(), self.finance)
        overdue.due_date = date.today() - timedelta(days=1)
        overdue.save(update_fields=["due_date", "updated_at"])
        Payment.objects.create(
            invoice=issued,
            payment_date=date(2025, 4, 20),
            amount=Decimal("59.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference_number="PAY-001",
        )

        self.client.force_authenticate(user=self.finance)
        response = self.client.get(reverse("billing-invoices-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_invoices"], 2)
        self.assertEqual(response.data["issued_invoices"], 0)
        self.assertEqual(response.data["partially_paid_invoices"], 1)
        self.assertEqual(response.data["overdue_invoices"], 1)
        self.assertEqual(response.data["payment_count"], 1)
        self.assertEqual(Decimal(response.data["total_paid"]), Decimal("59.00"))
        self.assertEqual(Decimal(response.data["total_estimated"]), estimate.total_amount)

    def test_invoice_list_refreshes_overdue_and_partial_statuses(self):
        overdue_invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        overdue_invoice.due_date = date.today() - timedelta(days=2)
        overdue_invoice.save(update_fields=["due_date", "updated_at"])

        partial_invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        partial_invoice.due_date = date.today() + timedelta(days=7)
        partial_invoice.save(update_fields=["due_date", "updated_at"])
        Payment.objects.create(
            invoice=partial_invoice,
            payment_date=date.today(),
            amount=Decimal("20.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference_number="PAY-PARTIAL",
        )

        self.client.force_authenticate(user=self.finance)
        response = self.client.get(reverse("billing-invoices-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data["results"]
        overdue_payload = next(item for item in payload if item["id"] == overdue_invoice.id)
        partial_payload = next(item for item in payload if item["id"] == partial_invoice.id)
        self.assertEqual(overdue_payload["status"], Invoice.Status.OVERDUE)
        self.assertEqual(partial_payload["status"], Invoice.Status.PARTIALLY_PAID)

    def test_public_estimate_endpoint_returns_sent_estimate(self):
        estimate = self._create_estimate()
        sent_estimate = CampaignEstimateService().share(estimate, actor=self.finance)

        response = self.client.get(f"/api/v1/public/estimates/{sent_estimate.approval_token_value}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], sent_estimate.id)
        self.assertEqual(response.data["status"], CampaignEstimate.Status.SENT)
        self.assertEqual(response.data["lines"][0]["media_unit_label"], self.unit.unit_code)

    def test_public_estimate_endpoint_allows_client_approval(self):
        estimate = self._create_estimate()
        sent_estimate = CampaignEstimateService().share(estimate, actor=self.finance)

        response = self.client.post(
            f"/api/v1/public/estimates/{sent_estimate.approval_token_value}/approve/",
            {"comment": "Approved by client."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sent_estimate.refresh_from_db()
        self.assertEqual(sent_estimate.status, CampaignEstimate.Status.APPROVED)
        self.assertIsNotNone(sent_estimate.approved_at)
        self.assertEqual(sent_estimate.client_response_comment, "Approved by client.")

    def test_public_estimate_endpoint_allows_client_rejection(self):
        estimate = self._create_estimate()
        sent_estimate = CampaignEstimateService().share(estimate, actor=self.finance)

        response = self.client.post(
            f"/api/v1/public/estimates/{sent_estimate.approval_token_value}/reject/",
            {"comment": "Please revise placement mix."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sent_estimate.refresh_from_db()
        self.assertEqual(sent_estimate.status, CampaignEstimate.Status.REJECTED)
        self.assertIsNotNone(sent_estimate.rejected_at)
        self.assertEqual(sent_estimate.client_response_comment, "Please revise placement mix.")

    def test_approved_estimate_line_is_locked_from_internal_edit(self):
        estimate = self._create_estimate(status=CampaignEstimate.Status.APPROVED)
        line = estimate.lines.get()
        self.client.force_authenticate(user=self.finance)

        response = self.client.patch(
            reverse("billing-campaign-estimate-lines-detail", args=[line.id]),
            {"description": "Updated after approval"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("estimate", response.data)

    def test_invoice_payment_endpoint_records_payment_and_updates_status(self):
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        invoice.due_date = date.today() + timedelta(days=10)
        invoice.save(update_fields=["due_date", "updated_at"])
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(
            reverse("billing-invoices-payments", args=[invoice.id]),
            {
                "amount": "40.00",
                "payment_date": str(date.today()),
                "payment_mode": Payment.Method.BANK_TRANSFER,
                "reference_number": "PMT-1001",
                "notes": "First installment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.assertEqual(invoice.payments.count(), 1)
        payment = invoice.payments.get()
        self.assertEqual(payment.notes, "First installment")

    def test_billing_summary_endpoint_returns_financial_dashboard_payload(self):
        self._create_estimate(status=CampaignEstimate.Status.APPROVED)
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        invoice.due_date = date.today() + timedelta(days=10)
        invoice.save(update_fields=["due_date", "updated_at"])
        Payment.objects.create(
            invoice=invoice,
            payment_date=date.today(),
            amount=Decimal("59.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference_number="SUMMARY-001",
            notes="Summary payment",
        )
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(reverse("billing-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_estimated", response.data)
        self.assertIn("total_approved_estimates", response.data)
        self.assertIn("total_invoiced", response.data)
        self.assertIn("total_collected", response.data)
        self.assertIn("outstanding_balance", response.data)
        self.assertIn("overdue_amount", response.data)

    def test_campaign_invoice_preview_uses_confirmed_booking_costs(self):
        self.booking.agreed_media_cost = Decimal("50000.00")
        self.booking.flex_cost = Decimal("8000.00")
        self.booking.installation_cost = Decimal("3500.00")
        self.booking.other_cost = Decimal("1500.00")
        self.booking.cost_notes = "Includes mounting support."
        self.booking.save(
            update_fields=[
                "agreed_media_cost",
                "flex_cost",
                "installation_cost",
                "other_cost",
                "cost_notes",
                "updated_at",
            ]
        )
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(f"/api/v1/campaigns/{self.campaign.id}/invoice-preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["can_generate"])
        self.assertEqual(response.data["confirmed_booking_count"], 1)
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("63000.00"))
        line = response.data["lines"][0]
        self.assertEqual(line["site_name"], self.site.name)
        self.assertEqual(line["media_unit_label"], self.unit.unit_code)
        self.assertEqual(Decimal(line["media_cost"]), Decimal("50000.00"))
        self.assertEqual(Decimal(line["flex_cost"]), Decimal("8000.00"))
        self.assertEqual(Decimal(line["installation_cost"]), Decimal("3500.00"))
        self.assertEqual(Decimal(line["other_cost"]), Decimal("1500.00"))
        self.assertEqual(Decimal(line["line_total"]), Decimal("63000.00"))

    def test_campaign_generate_invoice_creates_one_campaign_level_invoice(self):
        self.booking.agreed_media_cost = Decimal("50000.00")
        self.booking.flex_cost = Decimal("8000.00")
        self.booking.installation_cost = Decimal("3500.00")
        self.booking.other_cost = Decimal("1500.00")
        self.booking.save(
            update_fields=[
                "agreed_media_cost",
                "flex_cost",
                "installation_cost",
                "other_cost",
                "updated_at",
            ]
        )
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(f"/api/v1/campaigns/{self.campaign.id}/generate-invoice/", format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(id=response.data["id"])
        self.assertEqual(invoice.campaign, self.campaign)
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertEqual(invoice.total_amount, Decimal("63000.00"))
        line = invoice.lines.get()
        self.assertEqual(line.booking, self.booking)
        self.assertEqual(line.site_name, self.site.name)
        self.assertEqual(line.media_unit_label, self.unit.unit_code)
        self.assertEqual(line.media_cost, Decimal("50000.00"))
        self.assertEqual(line.flex_cost, Decimal("8000.00"))
        self.assertEqual(line.installation_cost, Decimal("3500.00"))
        self.assertEqual(line.other_cost, Decimal("1500.00"))
        self.assertEqual(line.line_total, Decimal("63000.00"))

    def test_campaign_generated_draft_can_be_issued_without_full_snapshot_fields(self):
        self.client.force_authenticate(user=self.finance)
        created = self.client.post(f"/api/v1/campaigns/{self.campaign.id}/generate-invoice/", format="json")

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(id=created.data["id"])
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertIsNone(invoice.supplier_profile)
        self.assertEqual(invoice.client_legal_name, self.client_user.email)

        issued = self.client.post(reverse("billing-invoices-issue", args=[invoice.id]), format="json")

        self.assertEqual(issued.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertIsNotNone(invoice.invoice_number)

    def test_download_pdf_endpoint_issues_campaign_generated_draft_invoice(self):
        self.client.force_authenticate(user=self.finance)
        self.campaign.name = "SP Smart & School <Admission>"
        self.site.name = "Main & Market <North>"
        self.unit.unit_code = "SP&ADM<001>"
        self.campaign.save(update_fields=["name", "updated_at"])
        self.site.save(update_fields=["name", "updated_at"])
        self.unit.save(update_fields=["unit_code", "updated_at"])

        created = self.client.post(f"/api/v1/campaigns/{self.campaign.id}/generate-invoice/", format="json")

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        invoice = Invoice.objects.get(id=created.data["id"])
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)

        response = self.client.get(reverse("billing-invoices-download-pdf", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertIsNotNone(invoice.invoice_number)

    @patch("apps.billing.services.logger.exception")
    @patch("apps.billing.services.issue_invoice", side_effect=RuntimeError("production issue failure"))
    def test_download_pdf_endpoint_returns_fallback_pdf_for_unexpected_issue_failure(
        self,
        _issue_invoice,
        _logger_exception,
    ):
        invoice = self._create_draft_invoice()
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(reverse("billing-invoices-download-pdf", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)

    def test_download_pdf_endpoint_preserves_business_validation_errors(self):
        invoice = self._create_draft_invoice()
        self.campaign.start_date = date.today() + timedelta(days=7)
        self.campaign.save(update_fields=["start_date", "updated_at"])
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(reverse("billing-invoices-download-pdf", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campaign", response.data)

    def test_campaign_generate_invoice_prevents_duplicate_campaign_invoices(self):
        self.client.force_authenticate(user=self.finance)
        first = self.client.post(f"/api/v1/campaigns/{self.campaign.id}/generate-invoice/", format="json")
        second = self.client.post(f"/api/v1/campaigns/{self.campaign.id}/generate-invoice/", format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campaign", second.data)
        self.assertEqual(Invoice.objects.filter(campaign=self.campaign).count(), 1)

    def test_campaign_invoice_preview_blocks_generation_before_campaign_start_date(self):
        future_campaign = Campaign.objects.create(
            name="Future Billing Campaign",
            code="CMP-FUTURE-001",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=35),
            budget=Decimal("125000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Future launch",
        )
        Booking.objects.create(
            campaign=future_campaign,
            media_unit=self.unit,
            start_date=future_campaign.start_date,
            end_date=future_campaign.end_date,
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(f"/api/v1/campaigns/{future_campaign.id}/invoice-preview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_generate"])
        self.assertEqual(
            response.data["message"],
            "Invoice can be generated only from the campaign start date onward.",
        )

    def test_campaign_generate_invoice_rejects_future_campaign_start_date(self):
        future_campaign = Campaign.objects.create(
            name="Future Billing Campaign",
            code="CMP-FUTURE-002",
            client=self.client_user,
            account_manager=self.sales,
            start_date=date.today() + timedelta(days=3),
            end_date=date.today() + timedelta(days=20),
            budget=Decimal("98000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Future launch",
        )
        Booking.objects.create(
            campaign=future_campaign,
            media_unit=self.unit,
            start_date=future_campaign.start_date,
            end_date=future_campaign.end_date,
            booked_rate=Decimal("42000.00"),
            status=Booking.Status.CONFIRMED,
        )
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(f"/api/v1/campaigns/{future_campaign.id}/generate-invoice/", format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campaign", response.data)
        self.assertEqual(
            response.data["campaign"][0],
            "Invoice can be generated only from the campaign start date onward.",
        )

    def test_supplier_profile_list_endpoint_works(self):
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(reverse("billing-supplier-profiles-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["gstin"], self.supplier.gstin)

    def test_draft_invoice_cannot_set_status_or_invoice_number_through_patch(self):
        invoice = self._create_draft_invoice()
        self.client.force_authenticate(user=self.finance)

        response = self.client.patch(
            reverse("billing-invoices-detail", args=[invoice.id]),
            {"status": Invoice.Status.ISSUED, "invoice_number": "MANUAL-001", "payment_terms": "Net 30"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertIsNone(invoice.invoice_number)
        self.assertEqual(invoice.payment_terms, "Net 30")

    def test_issued_invoice_line_cannot_be_casually_edited(self):
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        line = invoice.lines.get()
        self.client.force_authenticate(user=self.finance)

        response = self.client.patch(
            reverse("billing-invoice-lines-detail", args=[line.id]),
            {"description": "Updated line after issue"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("invoice", response.data)

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    def test_generate_pdf_endpoint_stores_private_document(self):
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(reverse("billing-invoices-generate-pdf", args=[invoice.id]), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invoice.refresh_from_db()
        self.assertEqual(invoice.pdf_file.name, "invoices/2025-26/INV_2025-26_0001.pdf")
        self.assertIn(invoice.pdf_file.name, MemoryPrivateDocumentStorage.saved_files)
        self.assertEqual(response.data["pdf_file"], invoice.pdf_file.name)

    def test_generate_pdf_endpoint_rejects_draft_invoice(self):
        invoice = self._create_draft_invoice()
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(reverse("billing-invoices-generate-pdf", args=[invoice.id]), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.data)

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    def test_pdf_link_endpoint_returns_short_lived_signed_url(self):
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        generate_invoice_pdf(invoice, actor=self.finance)
        self.client.force_authenticate(user=self.finance)

        response = self.client.get(reverse("billing-invoices-pdf-link", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["url"].startswith("https://private.example.com/documents/invoices/2025-26/"))
        self.assertIn("signature=test-signature", response.data["url"])
        self.assertIn("expires=900", response.data["url"])

    @patch("apps.billing.services.PrivateDocumentStorage", MemoryPrivateDocumentStorage)
    def test_pdf_link_endpoint_requires_object_permission(self):
        invoice = issue_invoice(self._create_draft_invoice(), self.finance)
        generate_invoice_pdf(invoice, actor=self.finance)
        outsider = self._create_user("other-client@example.com", "other_client", User.Role.CLIENT)
        self.client.force_authenticate(user=outsider)

        response = self.client.get(reverse("billing-invoices-pdf-link", args=[invoice.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
