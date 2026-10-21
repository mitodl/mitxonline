import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0072_add_testimonial_date_published"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coursepage",
            name="what_you_learn",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text="What you will learn from this course.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="programpage",
            name="what_you_learn",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text="What you will learn from this course.",
                null=True,
            ),
        ),
    ]
