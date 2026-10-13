import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("b2b", "0035_alter_organizationprovisioningaudit_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="contractpage",
            name="learner_records_opt_in",
            field=models.BooleanField(
                default=False,
                help_text="Whether the organization has asked for machine access to its learners' records under this contract. The credential reads identifiable learner records, so a contract existing is not an opt-in.",
            ),
        ),
        migrations.AddField(
            model_name="contractpage",
            name="learner_records_opt_in_recorded_on",
            field=models.DateTimeField(
                blank=True,
                help_text="When the learner records opt-in was last changed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="contractpage",
            name="learner_records_opt_in_recorded_by",
            field=models.ForeignKey(
                blank=True,
                help_text="The staff member who last changed the learner records opt-in.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
