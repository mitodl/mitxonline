"""Blocks search engine indexing for non-production environments."""

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag()
def noindex_meta():
    """Adds in noindex for non-production environments."""
    return (
        mark_safe("""<meta name="robots" content="noindex">""")
        if settings.ENVIRONMENT not in ("production", "prod")
        else ""
    )
