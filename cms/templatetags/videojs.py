"""
Generates a <video-js> tag. Expects the page object, which should use the
VideoPlayerConfigMixin.
"""

from django import template

register = template.Library()


@register.inclusion_tag("videojs_tag.html", name="videojs")
def videojs(page):
    return {"page": page}
