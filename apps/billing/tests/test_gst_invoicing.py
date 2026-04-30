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

from apps.billing.models import Invoice, InvoiceLine, InvoiceSequence, Payment, SupplierProfile
from apps.billing.services import generate_invoice_pdf, get_indian_financial_year, issue_invoice
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
        issued = issue_invoice(self._create_draft_invoice(), self.finance)
        overdue = issue_invoice(self._create_draft_invoice(), self.finance)
        overdue.status = Invoice.Status.OVERDUE
        overdue.save(update_fields=["status", "updated_at"])
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
        self.assertEqual(response.data["issued_invoices"], 1)
        self.assertEqual(response.data["overdue_invoices"], 1)
        self.assertEqual(response.data["payment_count"], 1)
        self.assertEqual(Decimal(response.data["total_paid"]), Decimal("59.00"))

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
