"""Wagtail hooks for courses app"""

from wagtail import hooks
from wagtail.admin.menu import MenuItem

from courses.wagtail_views import CourseTopicViewSet, TopicPairsViewSet


@hooks.register("register_admin_viewset")
def register_viewset():
    """
    Register `CourseTopicViewSet` in wagtail
    """
    return CourseTopicViewSet("topics")


@hooks.register("register_admin_viewset")
def register_viewset():
    """
    Register `CourseTopicViewSet` in wagtail
    """
    return TopicPairsViewSet("topic_pairs")


@hooks.register("register_admin_menu_item")
def register_calendar_menu_item():
    return MenuItem("Course Topics", "/cms/topics", icon_name="desktop")


@hooks.register("register_admin_menu_item")
def register_calendar_menu_item():
    return MenuItem("Topic Pairs", "/cms/topic_pairs", icon_name="desktop")

