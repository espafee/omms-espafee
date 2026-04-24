from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import Invoice, Payment
from apps.bookings.models import Booking
from apps.campaigns.models import Campaign, CampaignAsset
from apps.inventory.models import MediaSite, MediaUnit, RateCard
from apps.poe.models import ProofOfExecution, ProofOfExecutionMedia

User = get_user_model()


class AccessControlAPITests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"

        self.admin = self._create_user("admin@example.com", "admin_user", User.Role.ADMIN, is_staff=True)
        self.sales = self._create_user("sales@example.com", "sales_user", User.Role.SALES)
        self.operations = self._create_user("ops@example.com", "ops_user", User.Role.OPERATIONS)
        self.finance = self._create_user("finance@example.com", "finance_user", User.Role.FINANCE)
        self.client_one = self._create_user("client1@example.com", "client_one", User.Role.CLIENT)
        self.client_two = self._create_user("client2@example.com", "client_two", User.Role.CLIENT)

        self.site_one = MediaSite.objects.create(
            name="Airport Billboard",
            code="SITE-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Airport Road",
            city="Pune",
            state="Maharashtra",
            owner=self.operations,
        )
        self.site_two = MediaSite.objects.create(
            name="Metro Panel",
            code="SITE-002",
            site_type=MediaSite.SiteType.DIGITAL,
            address="Central Station",
            city="Mumbai",
            state="Maharashtra",
            owner=self.operations,
        )

        self.unit_one = MediaUnit.objects.create(
            site=self.site_one,
            unit_code="UNIT-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=True,
            monthly_rate=Decimal("50000.00"),
        )
        self.unit_two = MediaUnit.objects.create(
            site=self.site_two,
            unit_code="UNIT-002",
            face_count=1,
            width=Decimal("18.00"),
            height=Decimal("9.00"),
            status=MediaUnit.Status.AVAILABLE,
            is_illuminated=False,
            monthly_rate=Decimal("65000.00"),
        )

        self.rate_card_one = RateCard.objects.create(
            unit=self.unit_one,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            base_rate=Decimal("50000.00"),
            tax_percentage=Decimal("18.00"),
        )
        self.rate_card_two = RateCard.objects.create(
            unit=self.unit_two,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            base_rate=Decimal("65000.00"),
            tax_percentage=Decimal("18.00"),
        )

        self.campaign_one = Campaign.objects.create(
            name="Client One Summer Push",
            code="CMP-001",
            client=self.client_one,
            account_manager=self.sales,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Reach airport commuters",
        )
        self.campaign_two = Campaign.objects.create(
            name="Client Two Launch",
            code="CMP-002",
            client=self.client_two,
            account_manager=self.sales,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            budget=Decimal("120000.00"),
            status=Campaign.Status.ACTIVE,
            objective="Launch new product",
        )

        self.asset_one = CampaignAsset.objects.create(
            campaign=self.campaign_one,
            name="Airport Creative",
            asset_type="image",
            file_url="https://example.com/assets/campaign-one.jpg",
            is_approved=True,
        )
        self.asset_two = CampaignAsset.objects.create(
            campaign=self.campaign_two,
            name="Metro Creative",
            asset_type="image",
            file_url="https://example.com/assets/campaign-two.jpg",
            is_approved=True,
        )

        self.booking_one = Booking.objects.create(
            campaign=self.campaign_one,
            media_unit=self.unit_one,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            booked_rate=Decimal("55000.00"),
            status=Booking.Status.CONFIRMED,
        )
        self.booking_two = Booking.objects.create(
            campaign=self.campaign_two,
            media_unit=self.unit_two,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            booked_rate=Decimal("70000.00"),
            status=Booking.Status.CONFIRMED,
        )

        self.poe_one = ProofOfExecution.objects.create(
            booking=self.booking_one,
            executed_on=date.today(),
            checked_by=self.operations,
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )
        self.poe_two = ProofOfExecution.objects.create(
            booking=self.booking_two,
            executed_on=date.today(),
            checked_by=self.operations,
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
        )

        self.poe_media_one = ProofOfExecutionMedia.objects.create(
            poe_record=self.poe_one,
            media_url="https://example.com/poe/one.jpg",
            media_type="image",
            captured_at=timezone.now(),
        )
        self.poe_media_two = ProofOfExecutionMedia.objects.create(
            poe_record=self.poe_two,
            media_url="https://example.com/poe/two.jpg",
            media_type="image",
            captured_at=timezone.now(),
        )

        self.invoice_one = Invoice.objects.create(
            campaign=self.campaign_one,
            invoice_number="INV-001",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            subtotal=Decimal("55000.00"),
            tax_amount=Decimal("9900.00"),
            total_amount=Decimal("64900.00"),
            status=Invoice.Status.ISSUED,
        )
        self.invoice_two = Invoice.objects.create(
            campaign=self.campaign_two,
            invoice_number="INV-002",
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            subtotal=Decimal("70000.00"),
            tax_amount=Decimal("12600.00"),
            total_amount=Decimal("82600.00"),
            status=Invoice.Status.ISSUED,
        )

        self.payment_one = Payment.objects.create(
            invoice=self.invoice_one,
            payment_date=date.today(),
            amount=Decimal("10000.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference_number="PAY-001",
        )
        self.payment_two = Payment.objects.create(
            invoice=self.invoice_two,
            payment_date=date.today(),
            amount=Decimal("20000.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference_number="PAY-002",
        )

    def _create_user(self, email, username, role, is_staff=False):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            is_staff=is_staff,
        )

    def _authenticate(self, user):
        self.client.force_authenticate(user=user)

    def _extract_ids(self, response):
        return [item["id"] for item in response.data["results"]]

    def test_client_only_sees_own_campaigns_in_list(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("campaigns-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self._extract_ids(response), [self.campaign_one.id])

    def test_client_cannot_retrieve_another_clients_campaign(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("campaigns-detail", args=[self.campaign_two.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_only_sees_inventory_tied_to_their_bookings(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("inventory-units-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self._extract_ids(response), [self.unit_one.id])

    def test_client_only_sees_own_invoices(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("billing-invoices-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self._extract_ids(response), [self.invoice_one.id])

    def test_client_only_sees_own_poe_records(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("poe-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(self._extract_ids(response), [self.poe_one.id])

    def test_client_cannot_create_booking_even_for_own_campaign(self):
        self._authenticate(self.client_one)

        payload = {
            "campaign": self.campaign_one.id,
            "media_unit": self.unit_one.id,
            "start_date": str(date.today() + timedelta(days=20)),
            "end_date": str(date.today() + timedelta(days=30)),
            "booked_rate": "60000.00",
            "status": Booking.Status.PENDING,
            "remarks": "Attempted by client",
        }

        response = self.client.post(reverse("bookings-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sales_cannot_create_invoice(self):
        self._authenticate(self.sales)

        payload = {
            "campaign": self.campaign_one.id,
            "invoice_number": "INV-003",
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=15)),
            "subtotal": "1000.00",
            "tax_amount": "180.00",
            "total_amount": "1180.00",
            "status": Invoice.Status.ISSUED,
        }

        response = self.client.post(reverse("billing-invoices-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_finance_can_create_payment(self):
        self._authenticate(self.finance)

        payload = {
            "invoice": self.invoice_one.id,
            "payment_date": str(date.today()),
            "amount": "5000.00",
            "method": Payment.Method.CARD,
            "reference_number": "PAY-NEW",
        }

        response = self.client.post(reverse("billing-payments-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["invoice"], self.invoice_one.id)

    def test_client_campaign_summary_is_scoped(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("campaigns-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_campaigns"], 1)
        self.assertEqual(response.data["active_campaigns"], 1)
        self.assertEqual(response.data["total_bookings"], 1)
        self.assertEqual(response.data["approved_assets"], 1)
        self.assertEqual(response.data["total_budget"], "100000.00")

    def test_client_booking_summary_is_scoped(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("bookings-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_bookings"], 1)
        self.assertEqual(response.data["confirmed_bookings"], 1)
        self.assertEqual(response.data["unique_media_units"], 1)
        self.assertEqual(response.data["total_booked_value"], "55000.00")

    def test_client_billing_summary_is_scoped(self):
        self._authenticate(self.client_one)

        response = self.client.get(reverse("billing-invoices-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_invoices"], 1)
        self.assertEqual(response.data["issued_invoices"], 1)
        self.assertEqual(response.data["payment_count"], 1)
        self.assertEqual(response.data["total_invoiced"], "64900.00")
        self.assertEqual(response.data["total_paid"], "10000.00")
        self.assertEqual(response.data["outstanding_amount"], "54900.00")

    def test_finance_billing_summary_sees_global_totals(self):
        self._authenticate(self.finance)

        response = self.client.get(reverse("billing-invoices-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_invoices"], 2)
        self.assertEqual(response.data["issued_invoices"], 2)
        self.assertEqual(response.data["payment_count"], 2)
        self.assertEqual(response.data["total_invoiced"], "147500.00")
        self.assertEqual(response.data["total_paid"], "30000.00")
        self.assertEqual(response.data["outstanding_amount"], "117500.00")

    def test_only_admin_can_list_users(self):
        self._authenticate(self.sales)
        sales_response = self.client.get(reverse("users-list"))

        self.assertEqual(sales_response.status_code, status.HTTP_403_FORBIDDEN)

        self._authenticate(self.admin)
        admin_response = self.client.get(reverse("users-list"))

        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(admin_response.data["count"], 6)

    def test_token_endpoint_authenticates_with_email(self):
        response = self.client.post(
            reverse("token-obtain-pair"),
            {"email": self.client_one.email, "password": self.password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["id"], self.client_one.id)
