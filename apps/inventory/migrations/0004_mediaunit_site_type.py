from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_mediaunit_facing_direction"),
    ]

    operations = [
        migrations.AddField(
            model_name="mediaunit",
            name="site_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("single_side_view", "Single Side"),
                    ("both_side_view", "Both Side"),
                    ("back_to_back_double_site", "Back to Back Double Site"),
                ],
                max_length=40,
            ),
        ),
    ]
