from django.db import migrations, models


def normalize_media_unit_site_type(apps, schema_editor):
    media_unit = apps.get_model("inventory", "MediaUnit")
    media_unit.objects.filter(site_type="single_side_view").update(site_type="single_side")
    media_unit.objects.filter(site_type="both_side_view").update(site_type="both_side")
    media_unit.objects.filter(site_type="back_to_back_double_site").update(site_type="both_side")


def restore_media_unit_site_type(apps, schema_editor):
    media_unit = apps.get_model("inventory", "MediaUnit")
    media_unit.objects.filter(site_type="single_side").update(site_type="single_side_view")
    media_unit.objects.filter(site_type="both_side").update(site_type="both_side_view")


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_mediaunit_site_type"),
    ]

    operations = [
        migrations.RunPython(normalize_media_unit_site_type, restore_media_unit_site_type),
        migrations.AlterField(
            model_name="mediaunit",
            name="site_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("single_side", "Single Side"),
                    ("both_side", "Both Side"),
                ],
                max_length=40,
            ),
        ),
    ]
