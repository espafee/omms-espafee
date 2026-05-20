from django.db import migrations


def backfill_campaign_tenant(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    Campaign = apps.get_model("campaigns", "Campaign")
    default_tenant = Tenant.objects.filter(slug="vistaai-omms-beta").first() or Tenant.objects.filter(
        is_default=True,
        tenant_type="client",
    ).first()
    if not default_tenant:
        return

    for campaign in Campaign.objects.select_related("client").filter(tenant__isnull=True).iterator():
        campaign_tenant_id = getattr(campaign.client, "tenant_id", None) or default_tenant.id
        Campaign.objects.filter(pk=campaign.pk, tenant__isnull=True).update(tenant_id=campaign_tenant_id)


def clear_campaign_tenant(apps, schema_editor):
    Campaign = apps.get_model("campaigns", "Campaign")
    Campaign.objects.filter(tenant__slug="vistaai-omms-beta").update(tenant=None)


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0004_campaign_tenant"),
    ]

    operations = [
        migrations.RunPython(backfill_campaign_tenant, clear_campaign_tenant),
    ]
