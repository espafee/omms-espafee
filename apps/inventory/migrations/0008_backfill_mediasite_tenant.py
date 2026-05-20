from django.db import migrations


def backfill_media_site_tenant(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    MediaSite = apps.get_model("inventory", "MediaSite")
    default_tenant = Tenant.objects.filter(slug="vistaai-omms-beta").first() or Tenant.objects.filter(
        is_default=True,
        tenant_type="client",
    ).first()
    if default_tenant:
        MediaSite.objects.filter(tenant__isnull=True).update(tenant=default_tenant)


def clear_media_site_tenant(apps, schema_editor):
    MediaSite = apps.get_model("inventory", "MediaSite")
    MediaSite.objects.filter(tenant__slug="vistaai-omms-beta").update(tenant=None)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0007_mediasite_tenant"),
    ]

    operations = [
        migrations.RunPython(backfill_media_site_tenant, clear_media_site_tenant),
    ]
