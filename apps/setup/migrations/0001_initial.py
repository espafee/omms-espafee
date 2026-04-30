from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CompanyProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("company_name", models.CharField(blank=True, max_length=255)),
                ("legal_name", models.CharField(blank=True, max_length=255)),
                ("logo", models.ImageField(blank=True, null=True, upload_to="branding/logos/")),
                ("communication_email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("address", models.TextField(blank=True)),
                ("gstin", models.CharField(blank=True, max_length=15)),
                ("state_code", models.CharField(blank=True, max_length=10)),
                ("invoice_prefix", models.CharField(blank=True, default="INV", max_length=20)),
                ("bank_details", models.TextField(blank=True)),
                ("authorised_signatory", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "verbose_name": "Company profile",
                "verbose_name_plural": "Company profile",
            },
        ),
        migrations.CreateModel(
            name="OrganizationEmailSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("from_email", models.EmailField(blank=True, max_length=254)),
                ("reply_to_email", models.EmailField(blank=True, max_length=254)),
                ("smtp_host", models.CharField(blank=True, max_length=255)),
                ("smtp_port", models.PositiveIntegerField(default=587)),
                ("smtp_username", models.CharField(blank=True, max_length=255)),
                ("smtp_password_encrypted", models.TextField(blank=True)),
                ("use_tls", models.BooleanField(default=True)),
                ("use_ssl", models.BooleanField(default=False)),
                ("email_verified", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "Organization email settings",
                "verbose_name_plural": "Organization email settings",
            },
        ),
    ]
