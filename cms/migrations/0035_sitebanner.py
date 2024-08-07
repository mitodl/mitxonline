# Generated by Django 3.2.23 on 2024-03-27 14:37

import wagtail.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0034_add_search_image_to_course_and_program_page"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteBanner",
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
                ("message", wagtail.fields.RichTextField(max_length=255)),
            ],
        ),
    ]
