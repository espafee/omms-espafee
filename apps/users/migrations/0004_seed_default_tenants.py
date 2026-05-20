from django.db import migrations


def seed_default_tenants(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    User = apps.get_model("users", "User")

    platform_tenant, _ = Tenant.objects.get_or_create(
        slug="omms-platform",
        defaults={
            "name": "OMMS Platform",
            "tenant_type": "platform",
            "status": "active",
            "is_default": False,
        },
    )
    default_tenant, _ = Tenant.objects.get_or_create(
        slug="vistaai-omms-beta",
        defaults={
            "name": "VistaAi OMMS Beta",
            "tenant_type": "client",
            "status": "active",
            "is_default": True,
        },
    )

    Tenant.objects.filter(is_default=True).exclude(pk=default_tenant.pk).update(is_default=False)
    User.objects.filter(tenant__isnull=True, is_superuser=True).update(tenant=platform_tenant)
    User.objects.filter(tenant__isnull=True).update(tenant=default_tenant)


def clear_seeded_tenant_assignments(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(tenant__slug__in=["omms-platform", "vistaai-omms-beta"]).update(tenant=None)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_tenant"),
    ]

    operations = [
        migrations.RunPython(seed_default_tenants, clear_seeded_tenant_assignments),
    ]
