# Generated migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0077_add_paidprogram_model"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="courserun",
            name="courseware_url_path",
        ),
    ]
