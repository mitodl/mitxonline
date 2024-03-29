# Generated by Django 3.2.18 on 2023-07-26 19:20

import django.db.models.deletion
import modelcluster.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0028_add_instructor_page_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="InstructorPageLink",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.SmallIntegerField(blank=True, default=1, null=True)),
                (
                    "linked_instructor_page",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="cms.instructorpage",
                    ),
                ),
                (
                    "page",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="linked_instructors",
                        to="wagtailcore.page",
                    ),
                ),
            ],
        ),
    ]
