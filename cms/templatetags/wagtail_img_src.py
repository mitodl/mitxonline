"""Custom Wagtail templatetags"""
from urllib.parse import urlencode, urljoin

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag()
def wagtail_img_src(image_obj):
    """Returns the image source URL for a Wagtail Image object"""
    return "{url}?{qs}".format(
        url=urljoin(settings.MEDIA_URL, image_obj.file.name),
        qs=urlencode({"v": image_obj.file_hash}),
    )
