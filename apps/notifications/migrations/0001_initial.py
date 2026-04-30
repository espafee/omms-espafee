from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bookings", "0001_initial"),
        ("campaigns", "0003_campaignaccesstoken_token_value"),
        ("poe", "0003_proofofexecution_captured_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailNotificationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event_key", models.CharField(db_index=True, max_length=255, unique=True)),
                ("notification_type", models.CharField(choices=[("campaign_booked", "Campaign Booked"), ("poe_uploaded", "POE Uploaded")], max_length=30)),
                ("recipient_email", models.EmailField(blank=True, max_length=254)),
                ("recipient_name", models.CharField(blank=True, max_length=255)),
                ("subject", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_notification_logs", to="bookings.booking")),
                ("campaign", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_notification_logs", to="campaigns.campaign")),
                ("poe_media", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_notification_logs", to="poe.proofofexecutionmedia")),
                ("poe_record", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="email_notification_logs", to="poe.proofofexecution")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
