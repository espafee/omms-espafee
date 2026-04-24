from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bookings", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProofOfExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("executed_on", models.DateField()),
                (
                    "verification_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="poe_records",
                        to="bookings.booking",
                    ),
                ),
                (
                    "checked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="verified_poe_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProofOfExecutionMedia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("media_url", models.URLField()),
                ("media_type", models.CharField(default="image", max_length=20)),
                ("captured_at", models.DateTimeField()),
                (
                    "poe_record",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="media_items",
                        to="poe.proofofexecution",
                    ),
                ),
            ],
        ),
    ]
