from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bookings", "0001_initial"),
        ("campaigns", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_number", models.CharField(max_length=50, unique=True)),
                ("issue_date", models.DateField()),
                ("due_date", models.DateField()),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                ("tax_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("issued", "Issued"),
                            ("partially_paid", "Partially Paid"),
                            ("paid", "Paid"),
                            ("overdue", "Overdue"),
                        ],
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoices",
                        to="campaigns.campaign",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="InvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("description", models.CharField(max_length=255)),
                ("quantity", models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "booking",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoice_lines",
                        to="bookings.booking",
                    ),
                ),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="billing.invoice",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("payment_date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("bank_transfer", "Bank Transfer"),
                            ("cash", "Cash"),
                            ("card", "Card"),
                            ("cheque", "Cheque"),
                        ],
                        max_length=30,
                    ),
                ),
                ("reference_number", models.CharField(blank=True, max_length=100)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="billing.invoice",
                    ),
                ),
            ],
        ),
    ]
