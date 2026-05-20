from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import Invoice, Payment, SupplierProfile
from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.notifications.models import EmailNotificationLog, Notification
from apps.observability.models import AlertEvent, AlertRule, DashboardWidgetPreference, ImportExportJob, SavedOperationalView
from apps.observability.services import (
    _invoice_payment_export_payload,
    build_operations_summary,
    evaluate_alert_thresholds,
    save_dashboard_widget_preferences,
)
from apps.tenants.models import Tenant

User = get_user_model()


class FinanceOperationsTenantScopingTests(APITestCase):
    def setUp(self):
        self.password = "TestPass123!"
        self.platform_tenant = Tenant.objects.get(slug="omms-platform")
        self.alpha = Tenant.objects.create(name="Alpha Finance", slug="alpha-finance-ops")
        self.beta = Tenant.objects.create(name="Beta Finance", slug="beta-finance-ops")
        self.platform_admin = User.objects.create_superuser(
            email="platform-finops@omms.test",
            username="platform_finops",
            password=self.password,
            tenant=self.platform_tenant,
        )
        self.alpha_admin = self._user("alpha-admin-finops@omms.test", "alpha_admin_finops", User.Role.ADMIN, self.alpha)
        self.beta_admin = self._user("beta-admin-finops@omms.test", "beta_admin_finops", User.Role.ADMIN, self.beta)
        self.alpha_finance = self._user("alpha-finance-finops@omms.test", "alpha_finance_finops", User.Role.FINANCE, self.alpha)
        self.beta_finance = self._user("beta-finance-finops@omms.test", "beta_finance_finops", User.Role.FINANCE, self.beta)
        self.alpha_operations = self._user("alpha-ops-finops@omms.test", "alpha_ops_finops", User.Role.OPERATIONS, self.alpha)
        self.beta_operations = self._user("beta-ops-finops@omms.test", "beta_ops_finops", User.Role.OPERATIONS, self.beta)
        self.alpha_client = self._user("alpha-client-finops@omms.test", "alpha_client_finops", User.Role.CLIENT, self.alpha)
        self.beta_client = self._user("beta-client-finops@omms.test", "beta_client_finops", User.Role.CLIENT, self.beta)
        self.alpha_campaign = self._campaign("Alpha FinOps Campaign", "ALPHA-FINOPS-CMP", self.alpha_client, self.alpha_admin, self.alpha)
        self.beta_campaign = self._campaign("Beta FinOps Campaign", "BETA-FINOPS-CMP", self.beta_client, self.beta_admin, self.beta)
        self.alpha_site = self._site("Alpha FinOps Site", "ALPHA-FINOPS-SITE", self.alpha_admin, self.alpha)
        self.beta_site = self._site("Beta FinOps Site", "BETA-FINOPS-SITE", self.beta_admin, self.beta)
        self.alpha_unit = self._unit(self.alpha_site, "ALPHA-FINOPS-UNIT")
        self.beta_unit = self._unit(self.beta_site, "BETA-FINOPS-UNIT")
        self.alpha_booking = self._booking(self.alpha_campaign, self.alpha_unit)
        self.beta_booking = self._booking(self.beta_campaign, self.beta_unit)
        self.alpha_supplier = self._supplier(self.alpha, "Alpha Supplier", "27AAAAA0000A1Z5")
        self.beta_supplier = self._supplier(self.beta, "Beta Supplier", "27BBBBB0000B1Z5")
        self.alpha_invoice = self._invoice(self.alpha_campaign, self.alpha_supplier, "ALPHA-INV-001", Decimal("10000.00"))
        self.beta_invoice = self._invoice(self.beta_campaign, self.beta_supplier, "BETA-INV-001", Decimal("20000.00"))
        self.alpha_payment = Payment.objects.create(
            invoice=self.alpha_invoice,
            payment_date=date.today(),
            amount=Decimal("5000.00"),
            method=Payment.Method.BANK_TRANSFER,
            recorded_by=self.alpha_finance,
        )
        self.beta_payment = Payment.objects.create(
            invoice=self.beta_invoice,
            payment_date=date.today(),
            amount=Decimal("6000.00"),
            method=Payment.Method.BANK_TRANSFER,
            recorded_by=self.beta_finance,
        )

    def _user(self, email, username, role, tenant):
        return User.objects.create_user(
            email=email,
            username=username,
            password=self.password,
            role=role,
            tenant=tenant,
        )

    def _campaign(self, name, code, client, manager, tenant):
        return Campaign.objects.create(
            name=name,
            code=code,
            tenant=tenant,
            client=client,
            account_manager=manager,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=14),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
        )

    def _site(self, name, code, owner, tenant):
        return MediaSite.objects.create(
            name=name,
            code=code,
            tenant=tenant,
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Tenant Road",
            city="Jammu",
            state="Jammu and Kashmir",
            owner=owner,
        )

    def _unit(self, site, code):
        return MediaUnit.objects.create(
            site=site,
            unit_code=code,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            monthly_rate=Decimal("25000.00"),
            status=MediaUnit.Status.AVAILABLE,
        )

    def _booking(self, campaign, unit):
        return Booking.objects.create(
            campaign=campaign,
            media_unit=unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            booked_rate=Decimal("25000.00"),
            status=Booking.Status.CONFIRMED,
        )

    def _supplier(self, tenant, name, gstin):
        return SupplierProfile.objects.create(
            tenant=tenant,
            legal_name=name,
            gstin=gstin,
            address_line_1="Billing Road",
            city="Jammu",
            state="Jammu and Kashmir",
            postal_code="180001",
            state_code="01",
        )

    def _invoice(self, campaign, supplier, number, total):
        return Invoice.objects.create(
            campaign=campaign,
            supplier_profile=supplier,
            invoice_number=number,
            invoice_date=date.today() - timedelta(days=10),
            due_date=date.today() - timedelta(days=1),
            status=Invoice.Status.ISSUED,
            total_amount=total,
            grand_total=total,
        )

    def _result_ids(self, response):
        rows = response.data.get("results", response.data)
        return {row["id"] for row in rows}

    def test_finance_invoice_and_payment_visibility_is_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_finance)

        invoices = self.client.get(reverse("billing-invoices-list"))
        beta_detail = self.client.get(reverse("billing-invoices-detail", args=[self.beta_invoice.id]))
        payments = self.client.get(reverse("billing-payments-list"))

        self.assertEqual(invoices.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_invoice.id, self._result_ids(invoices))
        self.assertNotIn(self.beta_invoice.id, self._result_ids(invoices))
        self.assertEqual(beta_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn(self.alpha_payment.id, self._result_ids(payments))
        self.assertNotIn(self.beta_payment.id, self._result_ids(payments))

    def test_platform_superadmin_can_access_cross_tenant_finance(self):
        self.client.force_authenticate(user=self.platform_admin)

        invoices = self.client.get(reverse("billing-invoices-list"))
        beta_detail = self.client.get(reverse("billing-invoices-detail", args=[self.beta_invoice.id]))

        self.assertEqual(invoices.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_invoice.id, self._result_ids(invoices))
        self.assertIn(self.beta_invoice.id, self._result_ids(invoices))
        self.assertEqual(beta_detail.status_code, status.HTTP_200_OK)

    def test_supplier_profiles_are_tenant_scoped(self):
        self.client.force_authenticate(user=self.alpha_finance)

        response = self.client.get(reverse("billing-supplier-profiles-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.alpha_supplier.id, self._result_ids(response))
        self.assertNotIn(self.beta_supplier.id, self._result_ids(response))

    def test_import_export_jobs_are_tenant_scoped(self):
        alpha_job = ImportExportJob.objects.create(
            tenant=self.alpha,
            created_by=self.alpha_operations,
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
        )
        beta_job = ImportExportJob.objects.create(
            tenant=self.beta,
            created_by=self.beta_operations,
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
        )
        self.client.force_authenticate(user=self.alpha_operations)

        listing = self.client.get(reverse("observability-import-export-jobs-list"))
        beta_detail = self.client.get(reverse("observability-import-export-jobs-detail", args=[beta_job.id]))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertIn(alpha_job.id, self._result_ids(listing))
        self.assertNotIn(beta_job.id, self._result_ids(listing))
        self.assertEqual(beta_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_invoice_export_payload_cannot_include_cross_tenant_records(self):
        _filename, _headers, rows = _invoice_payment_export_payload({"_user": self.alpha_finance})

        exported_invoices = {row[0] for row in rows}
        self.assertIn(self.alpha_invoice.invoice_number, exported_invoices)
        self.assertNotIn(self.beta_invoice.invoice_number, exported_invoices)

    def test_operational_search_cannot_return_cross_tenant_results(self):
        self.client.force_authenticate(user=self.alpha_operations)

        response = self.client.get(
            reverse("observability-operational-search"),
            {"q": "Beta", "modules": "campaigns,sites,units,invoices,jobs,alerts,notifications"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 0)

    def test_dashboard_aggregation_uses_requesting_tenant(self):
        ImportExportJob.objects.create(
            tenant=self.alpha,
            created_by=self.alpha_operations,
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.PROCESSING,
        )
        ImportExportJob.objects.create(
            tenant=self.beta,
            created_by=self.beta_operations,
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.PROCESSING,
        )

        summary = build_operations_summary({"_user": self.alpha_operations})

        self.assertEqual(summary["kpis"]["active_jobs"], 1)
        self.assertEqual(summary["billing_intelligence"]["overdue_invoice_count"], 0)

    def test_notifications_and_alert_events_are_tenant_scoped(self):
        alpha_notification = Notification.objects.create(
            tenant=self.alpha,
            recipient_role=User.Role.OPERATIONS,
            event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
            title="Alpha alert",
        )
        beta_notification = Notification.objects.create(
            tenant=self.beta,
            recipient_role=User.Role.OPERATIONS,
            event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
            title="Beta alert",
        )
        rule = AlertRule.objects.create(
            name="Tenant alert visibility",
            metric=AlertRule.Metric.FAILED_IMPORT_EXPORT_JOBS,
            threshold=1,
            window_minutes=1440,
        )
        alpha_event = AlertEvent.objects.create(
            rule=rule,
            tenant=self.alpha,
            metric=rule.metric,
            observed_value=1,
            threshold=1,
            summary="Alpha event",
        )
        beta_event = AlertEvent.objects.create(
            rule=rule,
            tenant=self.beta,
            metric=rule.metric,
            observed_value=1,
            threshold=1,
            summary="Beta event",
        )
        self.client.force_authenticate(user=self.alpha_operations)

        notifications = self.client.get(reverse("notifications-inbox-list"))
        alerts = self.client.get(reverse("observability-alert-events-list"))

        self.assertEqual(notifications.status_code, status.HTTP_200_OK)
        self.assertIn(alpha_notification.id, self._result_ids(notifications))
        self.assertNotIn(beta_notification.id, self._result_ids(notifications))
        self.assertIn(alpha_event.id, self._result_ids(alerts))
        self.assertNotIn(beta_event.id, self._result_ids(alerts))

    def test_alert_cooldown_is_tenant_aware(self):
        rule, _created = AlertRule.objects.update_or_create(
            metric=AlertRule.Metric.FAILED_IMPORT_EXPORT_JOBS,
            defaults={
                "name": "Failed jobs tenant threshold",
                "threshold": 1,
                "window_minutes": 1440,
                "cooldown_minutes": 60,
                "is_enabled": True,
            },
        )
        ImportExportJob.objects.create(
            tenant=self.alpha,
            created_by=self.alpha_operations,
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
            completed_at=timezone.now(),
        )
        ImportExportJob.objects.create(
            tenant=self.beta,
            created_by=self.beta_operations,
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
            completed_at=timezone.now(),
        )

        created = evaluate_alert_thresholds(now=timezone.now())
        repeated = evaluate_alert_thresholds(now=timezone.now() + timedelta(minutes=5))

        tenants = {event.tenant_id for event in created if event.rule_id == rule.id}
        self.assertEqual(tenants, {self.alpha.id, self.beta.id})
        self.assertFalse([event for event in repeated if event.rule_id == rule.id])

    def test_saved_views_and_dashboard_preferences_store_requesting_tenant(self):
        self.client.force_authenticate(user=self.alpha_operations)

        saved_view = self.client.post(
            reverse("observability-saved-views-list"),
            {
                "name": "Alpha Failed Jobs",
                "view_type": SavedOperationalView.ViewType.SEARCH,
                "module": "jobs",
                "search_query": "failed",
                "filters": {"status": "failed"},
            },
            format="json",
        )
        profile = save_dashboard_widget_preferences(
            self.alpha_operations,
            [{"widget_key": "alerts", "is_visible": False, "sort_order": 2}],
        )

        self.assertEqual(saved_view.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SavedOperationalView.objects.get(id=saved_view.data["id"]).tenant, self.alpha)
        preference = DashboardWidgetPreference.objects.get(user=self.alpha_operations, widget_key="alerts")
        self.assertEqual(preference.tenant, self.alpha)
        self.assertFalse(next(widget for widget in profile["available_widgets"] if widget["key"] == "alerts")["is_visible"])
