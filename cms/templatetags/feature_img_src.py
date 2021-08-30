"""Custom Wagtail templatetags"""
from django import template

from cms.api import get_wagtail_img_src
from django.templatetags.static import static
from courses.constants import DEFAULT_COURSE_IMG_PATH

register = template.Library()


@register.simple_tag
def feature_img_src(product):
    """Get feature image for product"""
    feature_image = product.get('feature_image')
    if feature_image:
        return get_wagtail_img_src(feature_image)
    return static(DEFAULT_COURSE_IMG_PATH)
