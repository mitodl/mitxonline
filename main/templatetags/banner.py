"""Templatetags for rendering site banner"""

from django import template

from cms.models import SiteBanner

register = template.Library()


@register.inclusion_tag("../templates/partials/banner.html", takes_context=True)
def banner(context):
    """Return request context and banner."""

    return {
        "banner": SiteBanner.objects.order_by("-id").first(),
        "request": context["request"],
    }
