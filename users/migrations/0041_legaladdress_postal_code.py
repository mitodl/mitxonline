from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0040_add_is_etl_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="legaladdress",
            name="postal_code",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
    ]
