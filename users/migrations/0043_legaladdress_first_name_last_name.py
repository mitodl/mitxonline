from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0042_legaladdress_street_and_city"),
    ]

    operations = [
        migrations.AddField(
            model_name="legaladdress",
            name="first_name",
            field=models.CharField(blank=True, default="", max_length=60),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="legaladdress",
            name="last_name",
            field=models.CharField(blank=True, default="", max_length=60),
            preserve_default=False,
        ),
    ]
