"""Custom Wagtail templatetags"""

from django import template

from cms.api import get_wagtail_img_src

register = template.Library()


@register.simple_tag()
def wagtail_img_src(image_obj):
    """Returns the image source URL for a Wagtail Image object"""
    return get_wagtail_img_src(image_obj)
