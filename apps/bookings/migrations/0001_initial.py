from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("campaigns", "0001_initial"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("booked_rate", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("live", "Live"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("remarks", models.TextField(blank=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookings",
                        to="campaigns.campaign",
                    ),
                ),
                (
                    "media_unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookings",
                        to="inventory.mediaunit",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(
                fields=("campaign", "media_unit", "start_date", "end_date"),
                name="unique_booking_window_per_campaign_unit",
            ),
        ),
    ]
