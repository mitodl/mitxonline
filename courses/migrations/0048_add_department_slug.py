# Generated by Django 3.2.23 on 2024-03-27 14:49

from django.db import migrations, models


# Running this migration across 3 files to support the unique field, per django docs:
# https://docs.djangoproject.com/en/4.2/howto/writing-migrations/#migrations-that-add-unique-fields
class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0047_courses_and_programs_department_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="department",
            name="slug",
            field=models.SlugField(max_length=255, null=True),
        ),
    ]
