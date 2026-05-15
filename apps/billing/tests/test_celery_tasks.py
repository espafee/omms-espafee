from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.billing.models import Invoice, Payment
from apps.billing.tasks import mark_overdue_invoices
from apps.campaigns.models import Campaign

User = get_user_model()


class BillingCeleryTaskTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="billing-celery-admin@example.com",
            username="billing_celery_admin",
            password="x",
            role=User.Role.ADMIN,
        )
        self.client_user = User.objects.create_user(
            email="billing-celery-client@example.com",
            username="billing_celery_client",
            password="x",
            role=User.Role.CLIENT,
        )
        self.campaign = Campaign.objects.create(
            name="Billing Celery Campaign",
            code="CMP-BILLING-CELERY",
            client=self.client_user,
            account_manager=self.admin,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=10),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
        )

    def _create_invoice(self, *, status, due_date, total_amount=Decimal("1000.00")):
        return Invoice.objects.create(
            campaign=self.campaign,
            invoice_date=date.today(),
            due_date=due_date,
            status=status,
            total_amount=total_amount,
            grand_total=total_amount,
        )

    def test_mark_overdue_invoices_updates_only_open_past_due_invoices(self):
        past_due = self._create_invoice(
            status=Invoice.Status.ISSUED,
            due_date=date.today() - timedelta(days=1),
        )
        future_due = self._create_invoice(
            status=Invoice.Status.ISSUED,
            due_date=date.today() + timedelta(days=1),
        )
        paid_past_due = self._create_invoice(
            status=Invoice.Status.PAID,
            due_date=date.today() - timedelta(days=1),
        )
        Payment.objects.create(
            invoice=paid_past_due,
            payment_date=date.today(),
            amount=Decimal("1000.00"),
            method=Payment.Method.BANK_TRANSFER,
        )

        result = mark_overdue_invoices()

        self.assertEqual(result["updated_invoices"], 1)
        past_due.refresh_from_db()
        future_due.refresh_from_db()
        paid_past_due.refresh_from_db()
        self.assertEqual(past_due.status, Invoice.Status.OVERDUE)
        self.assertEqual(future_due.status, Invoice.Status.ISSUED)
        self.assertEqual(paid_past_due.status, Invoice.Status.PAID)
