"""Custom Wagtail templatetags"""

from django import template
from django.templatetags.static import static

from cms.api import get_wagtail_img_src
from courses.constants import DEFAULT_COURSE_IMG_PATH

register = template.Library()


@register.simple_tag
def feature_img_src(product_feature_image):
    """Get feature image for product"""
    if product_feature_image:
        return get_wagtail_img_src(product_feature_image)
    return static(DEFAULT_COURSE_IMG_PATH)
