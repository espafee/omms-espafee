from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.billing.models import Invoice, Payment
from apps.bookings.models import Booking
from apps.campaigns.models import Campaign
from apps.inventory.models import MediaSite, MediaUnit
from apps.notifications.models import EmailNotificationLog, Notification, NotificationPreference
from apps.notifications.services import NotificationService
from apps.observability.models import AlertEvent, AlertRule, ApiRequestLog, AuditEvent, DashboardWidgetPreference, ImportExportJob, SavedOperationalView
from apps.observability.services import (
    build_campaign_performance_analytics,
    build_dashboard_profile,
    build_operational_search,
    build_poe_sla_intelligence,
    build_poe_analytics,
    build_system_health_diagnostics,
    confirm_inventory_sites_import,
    evaluate_alert_thresholds,
    export_campaigns_csv,
    export_invoices_csv,
    process_export_job,
    process_inventory_sites_import,
    record_audit_event,
    retry_import_export_job,
    save_dashboard_widget_preferences,
    validate_inventory_sites_import,
)
from apps.observability.tasks import process_export_job_task
from apps.poe.models import ProofOfExecution
from apps.poe.services import get_poe_sla_status
from apps.billing.services import build_collection_efficiency_analytics

User = get_user_model()


class ObservabilityFoundationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "TestPass123!"
        self.admin = User.objects.create_user(
            email="admin-obs@example.com",
            username="admin_obs",
            password=self.password,
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.operations = User.objects.create_user(
            email="ops-obs@example.com",
            username="ops_obs",
            password=self.password,
            role=User.Role.OPERATIONS,
        )
        self.client_user = User.objects.create_user(
            email="client-obs@example.com",
            username="client_obs",
            password=self.password,
            role=User.Role.CLIENT,
        )
        self.site = MediaSite.objects.create(
            name="Observability Site",
            code="OBS-SITE-001",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Ring Road",
            city="Delhi",
            state="Delhi",
            latitude=Decimal("28.613900"),
            longitude=Decimal("77.209000"),
        )
        self.unit = MediaUnit.objects.create(
            site=self.site,
            unit_code="OBS-UNIT-001",
            face_count=1,
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            monthly_rate=Decimal("50000.00"),
        )
        self.campaign = Campaign.objects.create(
            name="Observability Campaign",
            code="OBS-CMP-001",
            client=self.client_user,
            account_manager=self.admin,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            budget=Decimal("100000.00"),
            status=Campaign.Status.ACTIVE,
        )
        self.booking = Booking.objects.create(
            campaign=self.campaign,
            media_unit=self.unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )

    @override_settings(OMMS_API_REQUEST_LOGGING_ENABLED=True, OMMS_SLOW_REQUEST_MS=0)
    def test_api_request_logging_middleware_records_safe_metadata(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("observability-diagnostics"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = ApiRequestLog.objects.filter(path__contains="/api/v1/observability/diagnostics/").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertTrue(log.is_slow)
        self.assertEqual(log.category, ApiRequestLog.Category.OBSERVABILITY)

    def test_audit_event_service_scrubs_sensitive_metadata(self):
        event = record_audit_event(
            event_type="security.login",
            entity_type="user",
            entity_id=self.admin.id,
            actor=self.admin,
            summary="Login recorded.",
            metadata={"token": "secret-token", "safe": "value"},
        )

        self.assertEqual(event.metadata["token"], "[redacted]")
        self.assertEqual(event.metadata["safe"], "value")

    def test_poe_analytics_counts_suspicious_missing_and_overdue(self):
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS,
            review_due_at=timezone.now() - timedelta(hours=2),
        )

        payload = build_poe_analytics()

        self.assertEqual(payload["suspicious_count"], 1)
        self.assertEqual(payload["missing_gps_count"], 1)
        self.assertEqual(payload["pending_review_count"], 1)
        self.assertEqual(payload["overdue_review_count"], 1)

    def test_poe_sla_indicator_marks_pending_warning_and_breach(self):
        now = timezone.now()
        warning_poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=25),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )
        breached_poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=49),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )

        self.assertEqual(get_poe_sla_status(warning_poe, now=now)["status"], "warning")
        self.assertEqual(get_poe_sla_status(breached_poe, now=now)["status"], "breached")

    def test_poe_sla_indicator_marks_suspicious_unresolved_faster(self):
        now = timezone.now()
        warning_poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=13),
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS,
        )
        breached_poe = ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=25),
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS,
        )

        self.assertEqual(get_poe_sla_status(warning_poe, now=now)["status"], "warning")
        self.assertEqual(get_poe_sla_status(breached_poe, now=now)["status"], "breached")
        self.assertTrue(get_poe_sla_status(breached_poe, now=now)["is_suspicious_unresolved"])

    def test_poe_sla_intelligence_aggregates_reviewer_workload(self):
        now = timezone.now()
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=49),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=2),
            checked_by=self.operations,
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=now - timedelta(hours=1),
            checked_by=self.operations,
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
            reviewed_at=now,
        )

        payload = build_poe_sla_intelligence(now=now)

        self.assertEqual(payload["breach_count"], 1)
        self.assertEqual(payload["unassigned_count"], 1)
        self.assertEqual(payload["oldest_pending"]["age_hours"], 49)
        reviewer = next(row for row in payload["reviewer_workload"] if row["reviewer"] == self.operations.email)
        self.assertEqual(reviewer["pending"], 1)
        self.assertEqual(reviewer["approved"], 1)

    def test_collection_efficiency_groups_overdue_age_buckets(self):
        invoice = Invoice.objects.create(
            campaign=self.campaign,
            invoice_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=10),
            total_amount=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            status=Invoice.Status.ISSUED,
        )
        Payment.objects.create(
            invoice=invoice,
            payment_date=date.today(),
            amount=Decimal("250.00"),
            method=Payment.Method.BANK_TRANSFER,
        )

        payload = build_collection_efficiency_analytics()

        self.assertEqual(payload["overdue_invoice_count"], 1)
        self.assertEqual(payload["overdue_amount"], Decimal("750.00"))
        bucket = next(item for item in payload["overdue_age_buckets"] if item["bucket"] == "8-15")
        self.assertEqual(bucket["count"], 1)
        self.assertEqual(bucket["amount"], Decimal("750.00"))
        self.assertEqual(payload["collection_efficiency_percentage"], 25)

    def test_campaign_performance_calculates_poe_completion_and_risk(self):
        second_site = MediaSite.objects.create(
            name="Second Campaign Site",
            code="OBS-SITE-002",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Ring Road",
            city="Delhi",
            state="Delhi",
        )
        second_unit = MediaUnit.objects.create(
            site=second_site,
            unit_code="OBS-UNIT-002",
            width=Decimal("20.00"),
            height=Decimal("10.00"),
            monthly_rate=Decimal("50000.00"),
        )
        Booking.objects.create(
            campaign=self.campaign,
            media_unit=second_unit,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            booked_rate=Decimal("50000.00"),
            status=Booking.Status.CONFIRMED,
        )
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.VERIFIED,
            reviewed_at=timezone.now(),
        )

        payload = build_campaign_performance_analytics(user=self.admin, queryset=Campaign.objects.filter(id=self.campaign.id))
        row = payload["campaigns"][0]

        self.assertEqual(row["booked_sites_count"], 2)
        self.assertEqual(row["sites_with_approved_poe"], 1)
        self.assertEqual(row["sites_missing_poe"], 1)
        self.assertEqual(row["pending_poe_count"], 1)
        self.assertEqual(row["poe_completion_percentage"], 50)
        self.assertFalse(row["invoice_generated"])
        self.assertIn("missing_poe", row["operational_delay_indicators"])
        self.assertIn(row["risk_status"], {"poe_risk", "critical"})

    def test_operational_search_returns_scoped_campaign_inventory_and_poe_results(self):
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )

        payload = build_operational_search(self.operations, {"q": "OBS", "modules": "campaigns,sites,units,poes"})
        modules = {item["module"] for item in payload["results"]}

        self.assertIn("campaigns", modules)
        self.assertIn("sites", modules)
        self.assertIn("units", modules)
        self.assertIn("poes", modules)
        self.assertEqual(payload["query"], "OBS")

    def test_operational_search_hides_finance_results_from_operations_role(self):
        Invoice.objects.create(
            campaign=self.campaign,
            invoice_number="INV-OBS-001",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=10),
            total_amount=Decimal("5000.00"),
            grand_total=Decimal("5000.00"),
            status=Invoice.Status.ISSUED,
        )

        operations_payload = build_operational_search(self.operations, {"q": "INV-OBS", "modules": "invoices,clients"})
        finance_payload = build_operational_search(self.admin, {"q": "INV-OBS", "modules": "invoices,clients"})

        self.assertEqual(operations_payload["results"], [])
        self.assertIn("invoices", {item["module"] for item in finance_payload["results"]})

    def test_saved_operational_views_are_owned_by_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/v1/observability/saved-views/",
            {
                "name": "Critical Campaigns",
                "view_type": "operations",
                "module": "campaigns",
                "filters": {"status": "critical", "module": "campaigns"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        saved_view = SavedOperationalView.objects.get()
        self.assertEqual(saved_view.user, self.admin)
        self.assertEqual(saved_view.filters["status"], "critical")

        self.client.force_authenticate(self.operations)
        list_response = self.client.get("/api/v1/observability/saved-views/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 0)

    def test_operational_search_endpoint_supports_module_filtering(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/v1/observability/operational-search/", {"q": "OBS", "modules": "campaigns"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["total"], 1)
        self.assertEqual({item["module"] for item in response.data["results"]}, {"campaigns"})

    def test_dashboard_profile_returns_role_specific_widgets(self):
        admin_profile = build_dashboard_profile(self.admin)
        operations_profile = build_dashboard_profile(self.operations)

        self.assertIn("billing_risk", admin_profile["active_widgets"])
        self.assertIn("poe_sla", operations_profile["active_widgets"])
        self.assertIn("import_export_jobs", operations_profile["active_widgets"])
        self.assertNotIn("billing_risk", operations_profile["active_widgets"])

    def test_dashboard_profile_protects_finance_widgets_for_field_staff(self):
        field_staff = User.objects.create_user(
            email="field-dashboard@example.com",
            username="field_dashboard",
            password=self.password,
            role=User.Role.FIELD_STAFF,
        )

        profile = build_dashboard_profile(field_staff)

        self.assertFalse(profile["can_view_finance"])
        self.assertFalse(profile["can_view_operations"])
        self.assertIn("assigned_work", profile["active_widgets"])
        self.assertNotIn("billing_risk", {widget["key"] for widget in profile["available_widgets"]})
        self.assertNotIn("operational_health", {widget["key"] for widget in profile["available_widgets"]})

    def test_dashboard_profile_client_visibility_is_restricted(self):
        profile = build_dashboard_profile(self.client_user)

        self.assertIn("client_campaign_status", profile["active_widgets"])
        self.assertIn("approved_poes", profile["active_widgets"])
        self.assertNotIn("alerts", {widget["key"] for widget in profile["available_widgets"]})
        self.assertFalse(profile["can_view_operations"])

    def test_dashboard_widget_preferences_save_and_read(self):
        updated = save_dashboard_widget_preferences(
            self.admin,
            [
                {"widget_key": "billing_risk", "is_visible": False, "sort_order": 4},
                {"widget_key": "campaign_performance", "is_visible": True, "sort_order": 1},
            ],
        )

        self.assertNotIn("billing_risk", updated["active_widgets"])
        self.assertTrue(
            DashboardWidgetPreference.objects.filter(
                user=self.admin,
                widget_key="billing_risk",
                is_visible=False,
            ).exists()
        )

    def test_dashboard_profile_endpoint_persists_preferences(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            "/api/v1/observability/dashboard-profile/",
            {"widgets": [{"widget_key": "billing_risk", "is_visible": False, "sort_order": 2}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("billing_risk", response.data["active_widgets"])
        self.assertIn("billing_risk", response.data["hidden_widgets"])

        get_response = self.client.get("/api/v1/observability/dashboard-profile/")
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("billing_risk", get_response.data["active_widgets"])
        self.assertIn("billing_risk", get_response.data["hidden_widgets"])

        reset_response = self.client.post(
            "/api/v1/observability/dashboard-profile/",
            {"action": "restore_defaults"},
            format="json",
        )

        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
        self.assertIn("billing_risk", reset_response.data["active_widgets"])

    def test_dashboard_profile_preserves_active_widget_order(self):
        updated = save_dashboard_widget_preferences(
            self.admin,
            [
                {"widget_key": "campaign_performance", "is_visible": True, "sort_order": 3},
                {"widget_key": "billing_risk", "is_visible": True, "sort_order": 1},
                {"widget_key": "alerts", "is_visible": True, "sort_order": 2},
            ],
        )

        active_subset = [key for key in updated["active_widgets"] if key in {"billing_risk", "alerts", "campaign_performance"}]
        self.assertEqual(active_subset, ["billing_risk", "alerts", "campaign_performance"])

    @patch("apps.observability.services.REQUIRED_DASHBOARD_WIDGETS", {"campaign_performance"})
    def test_dashboard_widget_preferences_keep_required_widgets_visible(self):
        updated = save_dashboard_widget_preferences(
            self.admin,
            [{"widget_key": "campaign_performance", "is_visible": False, "sort_order": 1}],
        )

        self.assertIn("campaign_performance", updated["active_widgets"])
        self.assertTrue(
            DashboardWidgetPreference.objects.filter(
                user=self.admin,
                widget_key="campaign_performance",
                is_visible=True,
            ).exists()
        )

    def test_campaign_performance_hides_billing_for_operations_role(self):
        Invoice.objects.create(
            campaign=self.campaign,
            invoice_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=10),
            total_amount=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            status=Invoice.Status.ISSUED,
        )

        payload = build_campaign_performance_analytics(user=self.operations, queryset=Campaign.objects.filter(id=self.campaign.id))
        row = payload["campaigns"][0]

        self.assertFalse(payload["can_view_billing"])
        self.assertEqual(row["billing_status"], "hidden")
        self.assertEqual(row["overdue_amount"], Decimal("0.00"))

    def test_diagnostics_are_admin_only(self):
        self.client.force_authenticate(self.client_user)
        denied = self.client.get(reverse("observability-diagnostics"))
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        allowed = self.client.get(reverse("observability-diagnostics"))
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertIn("database", allowed.data)
        self.assertIn("system_health", allowed.data)
        self.assertIn("environment", allowed.data)
        rendered = str(allowed.data).lower()
        self.assertNotIn("secret_key", rendered)
        self.assertNotIn("password", rendered)

    def test_system_health_diagnostics_reports_safe_status_flags(self):
        ApiRequestLog.objects.create(
            user=self.admin,
            company_name="VistaAi",
            method="GET",
            path="/api/v1/test/",
            status_code=500,
            duration_ms=1500,
            is_slow=True,
            category=ApiRequestLog.Category.OBSERVABILITY,
        )
        ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="VistaAi",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
        )

        payload = build_system_health_diagnostics()

        self.assertIn(payload["status"], {"healthy", "warning", "degraded"})
        self.assertTrue(payload["database"]["ok"])
        self.assertIn("configured", payload["redis"])
        self.assertEqual(payload["recent_failed_requests"], 1)
        self.assertEqual(payload["recent_slow_requests"], 1)
        self.assertEqual(payload["recent_failed_background_jobs"], 1)
        self.assertIn("database_engine", payload["deployment"])

    @patch("apps.observability.services.connection.cursor")
    def test_system_health_degraded_when_database_unavailable(self, cursor_mock):
        cursor_mock.side_effect = Exception("database unavailable")

        payload = build_system_health_diagnostics()

        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["database"]["ok"])

    @patch("apps.observability.services.ApiRequestLog.objects.filter")
    def test_system_health_degraded_when_diagnostic_queries_fail(self, filter_mock):
        filter_mock.side_effect = Exception("missing diagnostics table")

        payload = build_system_health_diagnostics()

        self.assertEqual(payload["status"], "degraded")
        self.assertTrue(payload["database"]["ok"])
        self.assertFalse(payload["database"]["diagnostic_queries_ok"])
        self.assertIn("diagnostic_queries_unavailable", payload["signals"])

    @patch("apps.observability.views.build_diagnostics_payload")
    def test_diagnostics_endpoint_returns_safe_fallback_on_payload_error(self, diagnostics_mock):
        diagnostics_mock.side_effect = RuntimeError("diagnostics failed")
        self.client.force_authenticate(self.admin)

        response = self.client.get(reverse("observability-diagnostics"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["system_health"]["status"], "degraded")
        self.assertEqual(response.data["cache"]["ok"], False)
        self.assertEqual(response.data["notification_retry_health"]["failed_count"], 0)

    @patch("apps.observability.services.build_system_health_diagnostics")
    def test_system_health_degraded_alert_creates_notification(self, health_mock):
        health_mock.return_value = {
            "status": "degraded",
            "api_status": "degraded",
            "database": {"ok": False},
            "redis": {"configured": True},
            "celery": {"enabled": True, "broker_configured": True, "eager": False, "mode": "enabled", "worker_ready": "unknown", "beat_configured": True},
            "recent_failed_requests": 25,
            "recent_slow_requests": 0,
            "recent_failed_background_jobs": 5,
            "active_jobs": 0,
            "last_successful_import": None,
            "last_successful_export": None,
            "signals": ["database_unavailable"],
            "deployment": {"environment_name": "test"},
        }
        AlertRule.objects.create(
            name="System health degraded",
            metric=AlertRule.Metric.SYSTEM_HEALTH_DEGRADED,
            threshold=1,
            window_minutes=15,
            cooldown_minutes=60,
            severity=AlertRule.Severity.CRITICAL,
        )

        events = evaluate_alert_thresholds()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metric, AlertRule.Metric.SYSTEM_HEALTH_DEGRADED)
        self.assertTrue(
            Notification.objects.filter(
                event_type=EmailNotificationLog.NotificationType.SYSTEM_DIAGNOSTIC_ALERT,
                recipient_role="admin",
            ).exists()
        )

    def test_notification_inbox_mark_read(self):
        notification = Notification.objects.create(
            recipient=self.operations,
            event_type=EmailNotificationLog.NotificationType.POE_UPLOADED,
            title="POE uploaded",
            message="A field upload arrived.",
        )
        self.client.force_authenticate(self.operations)

        response = self.client.post(reverse("notifications-inbox-mark-read", args=[notification.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_inventory_site_import_preview_validates_rows_without_creating_sites(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\n,Missing Code,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"

        job = validate_inventory_sites_import(upload, actor=self.admin)

        self.assertEqual(job.status, ImportExportJob.Status.PREVIEWED)
        self.assertEqual(job.rows_total, 1)
        self.assertEqual(job.rows_failed, 1)
        self.assertEqual(job.filters["summary"]["failed_rows"], 1)
        self.assertEqual(MediaSite.objects.filter(name="Missing Code").count(), 0)

    def test_inventory_site_import_preview_detects_duplicates_as_warnings(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\nOBS-SITE-001,Duplicate,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"

        job = validate_inventory_sites_import(upload, actor=self.admin)

        self.assertEqual(job.status, ImportExportJob.Status.PREVIEWED)
        self.assertEqual(job.rows_failed, 0)
        self.assertEqual(job.filters["summary"]["duplicate_rows"], 1)
        self.assertTrue(any("will be updated" in item["warning"] for item in job.filters["warnings"]))

    def test_inventory_site_import_preview_accepts_valid_rows_without_creating_sites(self):
        upload = BytesIO(
            b"site_code,site_name,site_type,address,city,state,site_latitude,site_longitude,unit_code,width,height,monthly_rate\n"
            b"OBS-SITE-002,New Site,billboard,Road,Delhi,Delhi,28.61,77.20,OBS-UNIT-002,20,10,50000\n"
        )
        upload.name = "sites.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        self.assertEqual(job.status, ImportExportJob.Status.PREVIEWED)
        self.assertEqual(job.rows_total, 1)
        self.assertEqual(job.rows_success, 1)
        self.assertEqual(job.rows_failed, 0)
        self.assertEqual(job.filters["summary"]["valid_rows"], 1)
        self.assertFalse(MediaSite.objects.filter(code="OBS-SITE-002").exists())
        self.assertFalse(MediaUnit.objects.filter(unit_code="OBS-UNIT-002").exists())

    def test_inventory_site_import_preview_detects_repeated_rows_and_unit_codes(self):
        upload = BytesIO(
            b"site_code,site_name,site_type,address,city,state,unit_code,width,height,monthly_rate\n"
            b"OBS-SITE-003,New Site,billboard,Road,Delhi,Delhi,OBS-UNIT-003,20,10,50000\n"
            b"OBS-SITE-003,New Site,billboard,Road,Delhi,Delhi,OBS-UNIT-003,20,10,50000\n"
        )
        upload.name = "inventory.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        self.assertEqual(job.rows_failed, 1)
        self.assertEqual(job.filters["summary"]["duplicate_rows"], 1)
        error_messages = " ".join(item["error"] for item in job.errors)
        self.assertIn("Repeated row", error_messages)
        self.assertIn("Repeated media unit code", error_messages)
        self.assertTrue(any("Repeated site code" in item["warning"] for item in job.filters["warnings"]))
        self.assertFalse(MediaUnit.objects.filter(unit_code="OBS-UNIT-003").exists())

    def test_inventory_site_import_preview_rejects_invalid_pricing(self):
        upload = BytesIO(
            b"site_code,site_name,site_type,address,city,state,unit_code,width,height,monthly_rate\n"
            b"OBS-SITE-004,Invalid Price,billboard,Road,Delhi,Delhi,OBS-UNIT-004,0,10,-500\n"
        )
        upload.name = "inventory.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        self.assertEqual(job.rows_failed, 1)
        self.assertTrue(any("monthly_rate cannot be negative" in item["error"] for item in job.errors))
        self.assertTrue(any("width must be greater than zero" in item["error"] for item in job.errors))
        self.assertFalse(MediaSite.objects.filter(code="OBS-SITE-004").exists())

    def test_inventory_site_import_preview_allows_missing_coordinates_as_warning(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\nOBS-SITE-005,No GPS,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        self.assertEqual(job.rows_failed, 0)
        self.assertEqual(job.filters["summary"]["warning_rows"], 1)
        self.assertTrue(any("Coordinates are empty" in item["warning"] for item in job.filters["warnings"]))
        self.assertFalse(MediaSite.objects.filter(code="OBS-SITE-005").exists())

    def test_inventory_import_confirm_requires_explicit_flag(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\nOBS-SITE-006,Confirm Flag,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        with self.assertRaisesMessage(ValueError, "Explicit confirmation"):
            confirm_inventory_sites_import(job, actor=self.admin, confirmed=False)

    def test_inventory_import_confirm_only_allows_previewed_jobs(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\nOBS-SITE-007,Status Guard,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)
        job.status = ImportExportJob.Status.COMPLETED
        job.save(update_fields=["status", "updated_at"])

        with self.assertRaisesMessage(ValueError, "Only previewed"):
            confirm_inventory_sites_import(job, actor=self.admin, confirmed=True)

    def test_inventory_import_confirm_rejects_cross_company_job(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\nOBS-SITE-008,Wrong Company,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)
        job.company_name = "Other Company"
        job.save(update_fields=["company_name", "updated_at"])

        with self.assertRaisesMessage(ValueError, "active company"):
            confirm_inventory_sites_import(job, actor=self.admin, confirmed=True)

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_confirmed_inventory_import_creates_inventory_and_counts_results(self):
        upload = BytesIO(
            b"site_code,site_name,site_type,address,city,state,site_latitude,site_longitude,unit_code,width,height,monthly_rate\n"
            b"OBS-SITE-009,Imported Site,billboard,Road,Delhi,Delhi,28.61,77.20,OBS-UNIT-009,20,10,50000\n"
        )
        upload.name = "inventory.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        confirmed = confirm_inventory_sites_import(job, actor=self.admin, confirmed=True)

        self.assertEqual(confirmed.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(confirmed.rows_success, 1)
        self.assertEqual(confirmed.rows_updated, 0)
        self.assertEqual(confirmed.rows_skipped, 0)
        self.assertEqual(confirmed.rows_failed, 0)
        self.assertTrue(MediaSite.objects.filter(code="OBS-SITE-009", latitude=Decimal("28.610000")).exists())
        self.assertTrue(MediaUnit.objects.filter(unit_code="OBS-UNIT-009").exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="inventory.import.completed", entity_id=str(confirmed.id)).exists())
        self.assertTrue(Notification.objects.filter(title="Inventory import completed").exists())

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_inventory_import_skips_failed_rows_and_imports_valid_rows(self):
        upload = BytesIO(
            b"site_code,site_name,site_type,address,city,state,unit_code,width,height,monthly_rate\n"
            b"OBS-SITE-010,Valid Site,billboard,Road,Delhi,Delhi,OBS-UNIT-010,20,10,50000\n"
            b",Broken Site,billboard,Road,Delhi,Delhi,OBS-UNIT-011,20,10,50000\n"
        )
        upload.name = "inventory.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        confirmed = confirm_inventory_sites_import(job, actor=self.admin, confirmed=True)

        self.assertEqual(confirmed.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(confirmed.rows_success, 1)
        self.assertEqual(confirmed.rows_failed, 1)
        self.assertTrue(MediaSite.objects.filter(code="OBS-SITE-010").exists())
        self.assertFalse(MediaUnit.objects.filter(unit_code="OBS-UNIT-011").exists())

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_repeated_confirmation_does_not_duplicate_inventory(self):
        upload = BytesIO(b"code,name,site_type,address,city,state\nOBS-SITE-012,Once Only,billboard,Road,Delhi,Delhi\n")
        upload.name = "sites.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)

        confirmed = confirm_inventory_sites_import(job, actor=self.admin, confirmed=True)
        with self.assertRaisesMessage(ValueError, "Only previewed"):
            confirm_inventory_sites_import(confirmed, actor=self.admin, confirmed=True)

        self.assertEqual(MediaSite.objects.filter(code="OBS-SITE-012").count(), 1)

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_retry_only_allows_failed_jobs(self):
        job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.COMPLETED,
        )

        with self.assertRaisesMessage(ValueError, "Only failed"):
            retry_import_export_job(job, actor=self.admin)

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_import_retry_creates_linked_job_and_preserves_failed_history(self):
        failed_job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.IMPORT,
            resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
            status=ImportExportJob.Status.FAILED,
            rows_total=1,
            rows_failed=1,
            preview_rows=[
                {
                    "row": 2,
                    "action": "create_site",
                    "site_code": "OBS-SITE-RETRY",
                    "unit_code": "OBS-UNIT-RETRY",
                    "data": {
                        "site_code": "OBS-SITE-RETRY",
                        "site_name": "Retry Site",
                        "site_type": MediaSite.SiteType.BILLBOARD,
                        "address": "Road",
                        "city": "Delhi",
                        "state": "Delhi",
                        "unit_code": "OBS-UNIT-RETRY",
                        "width": "20",
                        "height": "10",
                        "monthly_rate": "50000",
                    },
                    "status": "failed",
                    "message": "Transient failure.",
                    "errors": [{"row": 2, "error": "Row could not be imported safely."}],
                    "warnings": [],
                }
            ],
            errors=[{"row": 2, "error": "Row could not be imported safely."}],
        )

        retry_job = retry_import_export_job(failed_job, actor=self.admin)
        failed_job.refresh_from_db()

        self.assertEqual(retry_job.retry_of, failed_job)
        self.assertEqual(retry_job.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(retry_job.rows_success, 1)
        self.assertEqual(failed_job.status, ImportExportJob.Status.FAILED)
        self.assertEqual(failed_job.retry_count, 1)
        self.assertIsNotNone(failed_job.last_retry_at)
        self.assertTrue(MediaSite.objects.filter(code="OBS-SITE-RETRY").exists())
        self.assertTrue(AuditEvent.objects.filter(event_type="inventory.import.retry_requested", entity_id=str(failed_job.id)).exists())

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_import_retry_idempotency_skips_existing_inventory(self):
        MediaSite.objects.create(
            name="Existing Retry Site",
            code="OBS-SITE-RETRY-IDEMP",
            site_type=MediaSite.SiteType.BILLBOARD,
            address="Road",
            city="Delhi",
            state="Delhi",
            owner=self.admin,
        )
        failed_job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.IMPORT,
            resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
            status=ImportExportJob.Status.FAILED,
            rows_total=1,
            rows_failed=1,
            preview_rows=[
                {
                    "row": 2,
                    "action": "create_site",
                    "site_code": "OBS-SITE-RETRY-IDEMP",
                    "data": {
                        "site_code": "OBS-SITE-RETRY-IDEMP",
                        "site_name": "Existing Retry Site",
                        "site_type": MediaSite.SiteType.BILLBOARD,
                        "address": "Road",
                        "city": "Delhi",
                        "state": "Delhi",
                    },
                    "status": "failed",
                    "errors": [{"row": 2, "error": "Transient failure."}],
                }
            ],
        )

        retry_job = retry_import_export_job(failed_job, actor=self.admin)

        self.assertEqual(retry_job.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(retry_job.rows_skipped, 1)
        self.assertEqual(MediaSite.objects.filter(code="OBS-SITE-RETRY-IDEMP").count(), 1)

    def test_inventory_import_task_updates_result_counts(self):
        upload = BytesIO(
            b"site_code,site_name,site_type,address,city,state,unit_code,width,height,monthly_rate\n"
            b"OBS-SITE-013,Task Site,billboard,Road,Delhi,Delhi,OBS-UNIT-013,20,10,50000\n"
        )
        upload.name = "inventory.csv"
        job = validate_inventory_sites_import(upload, actor=self.admin)
        job.status = ImportExportJob.Status.CONFIRMED
        job.save(update_fields=["status", "updated_at"])

        processed = process_inventory_sites_import(job, actor=self.admin)

        self.assertEqual(processed.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(processed.rows_success, 1)
        self.assertEqual(processed.filters["summary"]["imported_count"], 1)
        self.assertIsNotNone(processed.started_at)
        self.assertIsNotNone(processed.completed_at)

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_campaign_export_creates_completed_job(self):
        job = export_campaigns_csv(actor=self.admin, filters={"status": Campaign.Status.ACTIVE})

        self.assertEqual(job.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(job.resource_type, ImportExportJob.ResourceType.CAMPAIGNS)
        self.assertEqual(job.rows_total, 1)
        self.assertTrue(job.output_file.name.endswith(".csv"))

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_invoice_payment_export_includes_payment_rows(self):
        invoice = Invoice.objects.create(
            campaign=self.campaign,
            invoice_number="INV-OBS-001",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=10),
            status=Invoice.Status.PAID,
            total_amount=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
        )
        Payment.objects.create(
            invoice=invoice,
            payment_date=date.today(),
            amount=Decimal("1000.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference_number="PAY-OBS-001",
        )

        job = export_invoices_csv(actor=self.admin, filters={"status": Invoice.Status.PAID})

        self.assertEqual(job.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(job.resource_type, ImportExportJob.ResourceType.INVOICES)
        self.assertEqual(job.rows_success, 1)
        self.assertIn("invoice-payments", job.output_file.name)

    def test_export_job_list_is_company_scoped(self):
        job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="Other Company",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.COMPLETED,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(f"/api/v1/observability/import-export-jobs/{job.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_endpoint_enforces_operations_permissions(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post("/api/v1/observability/import-export-jobs/campaigns/export/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_celery_export_task_writes_downloadable_file(self):
        job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.CONFIRMED,
        )

        result = process_export_job_task(job.id, actor_id=self.admin.id)
        job.refresh_from_db()

        self.assertEqual(result["status"], ImportExportJob.Status.COMPLETED)
        self.assertEqual(job.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(job.rows_success, 1)
        self.assertIn("campaigns", job.output_file.name)

        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/v1/observability/import-export-jobs/{job.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_failed_export_records_safe_error(self):
        job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.CONFIRMED,
        )

        def broken_builder(filters=None):
            raise RuntimeError("database secret detail")

        with patch.dict("apps.observability.services.EXPORT_PAYLOAD_BUILDERS", {ImportExportJob.ResourceType.CAMPAIGNS: broken_builder}):
            processed = process_export_job(job, actor=self.admin)

        self.assertEqual(processed.status, ImportExportJob.Status.FAILED)
        self.assertEqual(processed.rows_failed, 1)
        self.assertEqual(processed.errors, [{"error": "Export could not be generated safely."}])
        self.assertTrue(AuditEvent.objects.filter(event_type="export.failed", entity_id=str(processed.id)).exists())
        self.assertTrue(Notification.objects.filter(event_type=EmailNotificationLog.NotificationType.EXPORT_FAILED).exists())

    @override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False)
    def test_export_retry_regenerates_file_and_records_audit(self):
        failed_job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
            rows_failed=1,
            errors=[{"error": "Export could not be generated safely."}],
            filters={"export_filters": {"status": Campaign.Status.ACTIVE}},
        )

        retry_job = retry_import_export_job(failed_job, actor=self.admin)
        failed_job.refresh_from_db()

        self.assertEqual(retry_job.retry_of, failed_job)
        self.assertEqual(retry_job.status, ImportExportJob.Status.COMPLETED)
        self.assertEqual(retry_job.rows_success, 1)
        self.assertTrue(retry_job.output_file.name.endswith(".csv"))
        self.assertEqual(failed_job.retry_count, 1)
        self.assertTrue(AuditEvent.objects.filter(event_type="export.retry_requested", entity_id=str(failed_job.id)).exists())
        self.assertTrue(Notification.objects.filter(event_type=EmailNotificationLog.NotificationType.EXPORT_COMPLETED, title="Export completed").exists())

    def test_retry_endpoint_enforces_permissions_and_returns_retry_job(self):
        failed_job = ImportExportJob.objects.create(
            created_by=self.admin,
            company_name="",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
        )
        self.client.force_authenticate(self.client_user)
        forbidden_response = self.client.post(reverse("observability-import-export-jobs-retry", args=[failed_job.id]))
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        with override_settings(OMMS_ENABLE_BACKGROUND_JOBS=False):
            response = self.client.post(reverse("observability-import-export-jobs-retry", args=[failed_job.id]))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["retry_of"], failed_job.id)

    def test_alert_threshold_evaluation_respects_cooldown(self):
        rule = AlertRule.objects.create(
            name="Any slow request",
            metric=AlertRule.Metric.SLOW_REQUESTS,
            threshold=1,
            window_minutes=60,
            cooldown_minutes=60,
        )
        ApiRequestLog.objects.create(
            method="GET",
            path="/api/v1/test/",
            status_code=200,
            duration_ms=1500,
            is_slow=True,
            category=ApiRequestLog.Category.OTHER,
        )

        first = evaluate_alert_thresholds()
        second = evaluate_alert_thresholds()

        self.assertEqual(len([event for event in first if event.rule_id == rule.id]), 1)
        self.assertEqual(len([event for event in second if event.rule_id == rule.id]), 0)
        self.assertEqual(AlertEvent.objects.filter(rule=rule).count(), 1)

    def test_failed_import_export_threshold_creates_audit_and_notification(self):
        rule = AlertRule.objects.create(
            name="Failed jobs threshold",
            metric=AlertRule.Metric.FAILED_IMPORT_EXPORT_JOBS,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        ImportExportJob.objects.create(
            company_name="",
            job_type=ImportExportJob.JobType.EXPORT,
            resource_type=ImportExportJob.ResourceType.CAMPAIGNS,
            status=ImportExportJob.Status.FAILED,
        )

        events = evaluate_alert_thresholds()

        self.assertEqual(len([event for event in events if event.rule_id == rule.id]), 1)
        self.assertTrue(AuditEvent.objects.filter(event_type="alert.triggered", entity_id=str(rule.id)).exists())
        self.assertTrue(Notification.objects.filter(event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED, title__icontains=rule.name).exists())

    def test_poe_sla_breach_threshold_creates_audit_and_notification(self):
        rule = AlertRule.objects.create(
            name="POE SLA breach threshold",
            metric=AlertRule.Metric.POE_SLA_BREACHES,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=timezone.now() - timedelta(hours=49),
            verification_status=ProofOfExecution.VerificationStatus.PENDING,
        )

        events = evaluate_alert_thresholds()

        self.assertEqual(len([event for event in events if event.rule_id == rule.id]), 1)
        self.assertTrue(AuditEvent.objects.filter(event_type="alert.triggered", entity_id=str(rule.id)).exists())
        self.assertTrue(Notification.objects.filter(event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED, title__icontains=rule.name).exists())

    def test_overdue_invoice_threshold_notifies_finance_and_admin(self):
        rule = AlertRule.objects.create(
            name="Overdue invoice threshold",
            metric=AlertRule.Metric.OVERDUE_INVOICES,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        Invoice.objects.create(
            campaign=self.campaign,
            invoice_date=date.today() - timedelta(days=40),
            due_date=date.today() - timedelta(days=31),
            total_amount=Decimal("1500.00"),
            grand_total=Decimal("1500.00"),
            status=Invoice.Status.ISSUED,
        )

        events = evaluate_alert_thresholds()

        self.assertEqual(len([event for event in events if event.rule_id == rule.id]), 1)
        self.assertTrue(Notification.objects.filter(recipient_role="finance", title__icontains=rule.name).exists())
        self.assertTrue(Notification.objects.filter(recipient_role="admin", title__icontains=rule.name).exists())

    def test_campaign_risk_threshold_notifies_admin_and_operations(self):
        rule = AlertRule.objects.create(
            name="Critical campaign risk threshold",
            metric=AlertRule.Metric.CAMPAIGNS_AT_RISK,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
            severity=AlertRule.Severity.CRITICAL,
        )
        self.campaign.end_date = date.today() + timedelta(days=1)
        self.campaign.save(update_fields=["end_date", "updated_at"])
        ProofOfExecution.objects.create(
            booking=self.booking,
            executed_on=date.today(),
            captured_at=timezone.now(),
            verification_status=ProofOfExecution.VerificationStatus.SUSPICIOUS,
        )

        events = evaluate_alert_thresholds()

        self.assertEqual(len([event for event in events if event.rule_id == rule.id]), 1)
        self.assertTrue(Notification.objects.filter(recipient_role="admin", title__icontains=rule.name).exists())
        self.assertTrue(Notification.objects.filter(recipient_role="operations", title__icontains=rule.name).exists())

    def test_failed_api_request_threshold_uses_24h_window(self):
        rule = AlertRule.objects.create(
            name="Failed API threshold",
            metric=AlertRule.Metric.FAILED_API_REQUESTS,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        ApiRequestLog.objects.create(
            method="GET",
            path="/api/v1/billing/",
            status_code=500,
            duration_ms=200,
            is_slow=False,
            category=ApiRequestLog.Category.BILLING,
        )

        events = evaluate_alert_thresholds()

        self.assertEqual(len([event for event in events if event.rule_id == rule.id]), 1)

    def test_disabled_alert_threshold_does_not_trigger(self):
        AlertRule.objects.create(
            name="Disabled failed jobs",
            metric=AlertRule.Metric.FAILED_IMPORT_EXPORT_JOBS,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
            is_enabled=False,
        )
        ImportExportJob.objects.create(
            company_name="",
            job_type=ImportExportJob.JobType.IMPORT,
            resource_type=ImportExportJob.ResourceType.INVENTORY_SITES,
            status=ImportExportJob.Status.FAILED,
        )

        self.assertEqual(evaluate_alert_thresholds(), [])
        self.assertFalse(AlertEvent.objects.exists())

    def test_alert_rule_api_exposes_current_value_and_allows_admin_updates(self):
        rule = AlertRule.objects.create(
            name="Failed API threshold",
            metric=AlertRule.Metric.FAILED_API_REQUESTS,
            threshold=3,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        ApiRequestLog.objects.create(
            method="GET",
            path="/api/v1/operations/",
            status_code=500,
            duration_ms=200,
            is_slow=False,
            category=ApiRequestLog.Category.OBSERVABILITY,
        )
        self.client.force_authenticate(self.admin)

        list_response = self.client.get(reverse("observability-alert-rules-list"))
        patch_response = self.client.patch(reverse("observability-alert-rules-detail", args=[rule.id]), {"threshold": 1, "is_enabled": False}, format="json")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        listed_rule = next(item for item in list_response.data["results"] if item["id"] == rule.id)
        self.assertEqual(listed_rule["current_value"], 1)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data["threshold"], 1)
        self.assertFalse(patch_response.data["is_enabled"])

    def test_client_cannot_access_alert_rules(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(reverse("observability-alert-rules-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operations_can_acknowledge_alert_event(self):
        rule = AlertRule.objects.create(
            name="Failed API threshold",
            metric=AlertRule.Metric.FAILED_API_REQUESTS,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        event = AlertEvent.objects.create(
            rule=rule,
            metric=rule.metric,
            observed_value=2,
            threshold=1,
            severity=AlertRule.Severity.WARNING,
            summary="Failed API threshold: observed 2, threshold 1.",
        )
        self.client.force_authenticate(self.operations)

        response = self.client.post(reverse("observability-alert-events-acknowledge", args=[event.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.acknowledged_by, self.operations)
        self.assertIsNotNone(event.acknowledged_at)
        self.assertTrue(response.data["is_acknowledged"])
        self.assertEqual(response.data["acknowledged_by_email"], self.operations.email)
        self.assertTrue(AuditEvent.objects.filter(event_type="alert.acknowledged", entity_id=str(event.id)).exists())

    def test_client_cannot_acknowledge_alert_event(self):
        rule = AlertRule.objects.create(
            name="Failed API threshold",
            metric=AlertRule.Metric.FAILED_API_REQUESTS,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        event = AlertEvent.objects.create(
            rule=rule,
            metric=rule.metric,
            observed_value=2,
            threshold=1,
            severity=AlertRule.Severity.WARNING,
            summary="Failed API threshold: observed 2, threshold 1.",
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(reverse("observability-alert-events-acknowledge", args=[event.id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        event.refresh_from_db()
        self.assertIsNone(event.acknowledged_at)

    def test_alert_rule_api_exposes_cooldown_visibility(self):
        rule = AlertRule.objects.create(
            name="Failed API threshold",
            metric=AlertRule.Metric.FAILED_API_REQUESTS,
            threshold=1,
            window_minutes=1440,
            cooldown_minutes=60,
        )
        AlertEvent.objects.create(
            rule=rule,
            metric=rule.metric,
            observed_value=2,
            threshold=1,
            severity=AlertRule.Severity.WARNING,
            summary="Failed API threshold: observed 2, threshold 1.",
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(reverse("observability-alert-rules-detail", args=[rule.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["cooldown_until"])
        self.assertGreaterEqual(response.data["cooldown_remaining_minutes"], 0)

    def test_notification_preferences_can_disable_in_app_notification_for_user(self):
        NotificationPreference.objects.create(
            user=self.operations,
            notification_type=EmailNotificationLog.NotificationType.POE_UPLOADED,
            in_app_enabled=False,
            email_enabled=True,
        )

        NotificationService().create_internal_notification(
            recipient=self.operations,
            event_type=EmailNotificationLog.NotificationType.POE_UPLOADED,
            title="Muted",
        )

        self.assertFalse(Notification.objects.filter(recipient=self.operations, title="Muted").exists())

    def test_public_health_endpoint_is_accessible(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

    def test_role_activity_endpoint_aggregates_audit_events(self):
        record_audit_event(
            event_type="invoice.issued",
            entity_type="invoice",
            entity_id="1",
            actor=self.admin,
            summary="Invoice issued.",
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(reverse("observability-role-activity"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_events"], 1)

    def test_operations_summary_returns_kpis_charts_timeline_and_health(self):
        ApiRequestLog.objects.create(
            method="GET",
            path="/api/v1/operations/",
            status_code=500,
            duration_ms=1500,
            is_slow=True,
            category=ApiRequestLog.Category.OBSERVABILITY,
        )
        Notification.objects.create(
            recipient_role="operations",
            event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
            title="Alert",
            severity=Notification.Severity.WARNING,
        )
        record_audit_event(
            event_type="billing.invoice",
            entity_type="invoice",
            actor=self.admin,
            severity=AuditEvent.Severity.WARNING,
            summary="Invoice activity.",
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("observability-operations-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("kpis", response.data)
        self.assertIn("charts", response.data)
        self.assertIn("timeline", response.data)
        self.assertIn("system_health", response.data)
        self.assertIn("poe_sla", response.data)
        self.assertIn("poe_sla_warnings", response.data["kpis"])
        self.assertIn("billing_intelligence", response.data)
        self.assertIn("campaign_performance", response.data)
        self.assertIn("campaigns_poe_risk", response.data["kpis"])
        self.assertIn("critical_campaigns", response.data["kpis"])
        self.assertIn("campaign_poe_completion_trend", response.data["charts"])
        self.assertGreaterEqual(response.data["kpis"]["failed_requests"], 1)
        self.assertTrue(response.data["charts"]["request_activity"])
        self.assertTrue(response.data["timeline"])

    @patch("apps.observability.views.build_operations_summary")
    def test_operations_summary_returns_safe_fallback_on_aggregation_error(self, summary_mock):
        summary_mock.side_effect = RuntimeError("aggregation failed")
        self.client.force_authenticate(self.admin)

        response = self.client.get(reverse("observability-operations-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["system_health"]["status"], "degraded")
        self.assertEqual(response.data["kpis"]["active_jobs"], 0)
        self.assertIn("Operations summary is temporarily unavailable.", response.data["warnings"])

    def test_operations_summary_hides_billing_intelligence_from_operations_role(self):
        Invoice.objects.create(
            campaign=self.campaign,
            invoice_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=10),
            total_amount=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            status=Invoice.Status.ISSUED,
        )
        self.client.force_authenticate(self.operations)

        response = self.client.get(reverse("observability-operations-summary"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kpis"]["overdue_invoices"], 0)
        self.assertEqual(response.data["billing_intelligence"]["top_overdue_clients"], [])

    def test_operations_summary_filters_audit_by_role_and_notification_type(self):
        record_audit_event(
            event_type="ops.admin",
            entity_type="operations",
            actor=self.admin,
            summary="Admin operation.",
        )
        record_audit_event(
            event_type="ops.operations",
            entity_type="operations",
            actor=self.operations,
            summary="Operations action.",
        )
        Notification.objects.create(
            recipient_role="operations",
            event_type=EmailNotificationLog.NotificationType.EXPORT_COMPLETED,
            title="Export completed",
        )
        Notification.objects.create(
            recipient_role="operations",
            event_type=EmailNotificationLog.NotificationType.ALERT_TRIGGERED,
            title="Alert",
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("observability-operations-summary"),
            {"role": User.Role.OPERATIONS, "notification_type": EmailNotificationLog.NotificationType.EXPORT_COMPLETED},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["actor"] == self.operations.email for item in response.data["timeline"]))
        self.assertEqual(response.data["kpis"]["notifications_today"], 1)

    def test_operations_summary_is_permission_scoped(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(reverse("observability-operations-summary"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
