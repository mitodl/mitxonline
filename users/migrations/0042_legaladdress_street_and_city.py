from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0041_legaladdress_postal_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="legaladdress",
            name="street_address_1",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="legaladdress",
            name="street_address_2",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="legaladdress",
            name="city",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
    ]
