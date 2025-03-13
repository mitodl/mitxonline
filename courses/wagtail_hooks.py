"""Wagtail hooks for courses app"""

from wagtail import hooks
from wagtail.admin.menu import MenuItem

from courses.wagtail_views import CourseTopicViewSet


@hooks.register("register_admin_viewset")
def register_viewset():
    """
    Register `CourseTopicViewSet` in wagtail
    """
    return CourseTopicViewSet("topics")
