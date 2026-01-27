# Generated migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0078_add_has_courseware_url"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="courserun",
            name="courseware_url_path",
        ),
    ]
