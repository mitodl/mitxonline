import html
import re

from django.db import migrations, models
from django.utils.html import strip_tags

BLOCK_BREAK = re.compile(r"<br\s*/?>|</(p|div|h[1-6]|li|blockquote)>", re.IGNORECASE)
EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def html_to_text(value):
    """Return the text of a rich text value, with one line per block."""

    text = BLOCK_BREAK.sub("\n", value)
    text = html.unescape(strip_tags(text))
    lines = [line.strip() for line in text.splitlines()]
    return EXTRA_BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def strip_description_html(apps, schema_editor):
    OrganizationPage = apps.get_model("b2b", "OrganizationPage")
    for organization in OrganizationPage.objects.exclude(description=""):
        text = html_to_text(organization.description)
        if text != organization.description:
            OrganizationPage.objects.filter(pk=organization.pk).update(description=text)


class Migration(migrations.Migration):
    dependencies = [
        ("b2b", "0032_org_key_prefix_blank_means_no_prefix"),
    ]

    operations = [
        migrations.RunPython(strip_description_html, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="organizationpage",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Any useful extra information about the organization",
            ),
        ),
    ]
