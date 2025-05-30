# Generated by Django 4.2.21 on 2025-05-09 14:28

import django.db.models.deletion
import wagtail.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0001_add_orgs_and_contracts_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="contractpage",
            name="enrollment_fixed_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="The fixed price for enrollment under this contract. (Set to zero or leave blank for free.)",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="contractpage",
            name="max_learners",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="The maximum number of learners allowed under this contract. (Set to zero or leave blank for unlimited.)",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="contractpage",
            name="description",
            field=wagtail.fields.RichTextField(
                blank=True, help_text="Any useful extra information about the contract."
            ),
        ),
        migrations.AlterField(
            model_name="contractpage",
            name="integration_type",
            field=models.CharField(
                choices=[("sso", "SSO"), ("non-sso", "Non-SSO")],
                help_text="The type of integration for this contract.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="contractpage",
            name="name",
            field=models.CharField(
                help_text="The name of the contract.", max_length=255
            ),
        ),
        migrations.AlterField(
            model_name="contractpage",
            name="organization",
            field=models.ForeignKey(
                help_text="The organization this contract is with.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contracts",
                to="b2b.organizationpage",
            ),
        ),
    ]
