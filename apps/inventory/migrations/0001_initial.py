from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MediaSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("code", models.CharField(max_length=50, unique=True)),
                (
                    "site_type",
                    models.CharField(
                        choices=[
                            ("billboard", "Billboard"),
                            ("transit", "Transit"),
                            ("street_furniture", "Street Furniture"),
                            ("digital", "Digital"),
                        ],
                        max_length=30,
                    ),
                ),
                ("address", models.CharField(max_length=500)),
                ("city", models.CharField(max_length=100)),
                ("state", models.CharField(max_length=100)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="owned_sites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MediaUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("unit_code", models.CharField(max_length=50, unique=True)),
                ("face_count", models.PositiveIntegerField(default=1)),
                ("width", models.DecimalField(decimal_places=2, max_digits=8)),
                ("height", models.DecimalField(decimal_places=2, max_digits=8)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("available", "Available"),
                            ("reserved", "Reserved"),
                            ("maintenance", "Maintenance"),
                            ("retired", "Retired"),
                        ],
                        default="available",
                        max_length=20,
                    ),
                ),
                ("is_illuminated", models.BooleanField(default=False)),
                ("monthly_rate", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="units",
                        to="inventory.mediasite",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RateCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("base_rate", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_percentage", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rate_cards",
                        to="inventory.mediaunit",
                    ),
                ),
            ],
            options={"ordering": ["-start_date"]},
        ),
    ]
