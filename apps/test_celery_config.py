from django.conf import settings
from django.test import SimpleTestCase

from config.celery import app


class CeleryConfigurationTests(SimpleTestCase):
    def test_safe_recurring_tasks_are_registered_in_beat_schedule(self):
        self.assertEqual(
            settings.CELERY_BEAT_SCHEDULE["mark-overdue-invoices-nightly"]["task"],
            "apps.billing.tasks.mark_overdue_invoices",
        )
        self.assertEqual(
            settings.CELERY_BEAT_SCHEDULE["deactivate-expired-campaign-access-tokens-nightly"]["task"],
            "apps.campaigns.tasks.deactivate_expired_campaign_access_tokens",
        )

    def test_celery_uses_json_and_env_driven_broker_settings(self):
        self.assertEqual(app.conf.task_serializer, "json")
        self.assertEqual(app.conf.result_serializer, "json")
        self.assertEqual(app.conf.accept_content, ["json"])
        self.assertEqual(app.conf.broker_url, settings.CELERY_BROKER_URL)
        self.assertEqual(app.conf.result_backend, settings.CELERY_RESULT_BACKEND)
