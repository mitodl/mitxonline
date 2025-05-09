# Generated by Django 4.2.18 on 2025-03-12 15:49

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0059_alter_coursestopic_options_alter_coursestopic_parent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coursestopic",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="child_topics",
                to="courses.coursestopic",
            ),
        ),
    ]
