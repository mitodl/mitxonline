from django.db import migrations, models

# Until this migration, a blank org_key_prefix fell back to UAI_ when contract
# run keys were built. Blank now means no prefix, so existing blank prefixes
# are set to the UAI_ they were already getting.
UAI_COURSEWARE_ID_PREFIX = "UAI_"


def set_blank_prefixes_to_uai(apps, schema_editor):
    OrganizationPage = apps.get_model("b2b", "OrganizationPage")
    OrganizationPage.objects.filter(org_key_prefix="").update(
        org_key_prefix=UAI_COURSEWARE_ID_PREFIX
    )


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0031_organizationprovisioningaudit"),
    ]

    operations = [
        migrations.RunPython(set_blank_prefixes_to_uai, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="organizationpage",
            name="org_key_prefix",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Prepended to the org key in courseware IDs, e.g. UAI_. "
                    "Blank means no prefix."
                ),
                max_length=30,
            ),
        ),
    ]
