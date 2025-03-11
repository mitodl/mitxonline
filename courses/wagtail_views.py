"""Wagtail admin views"""

from wagtail.admin.viewsets.model import ModelViewSet

from cms.models import TopicsPair
from courses.models import CoursesTopic


class CourseTopicViewSet(ModelViewSet):
    """Wagtail ModelViewSet for CourseTopic"""

    model = CoursesTopic
    icon = "desktop"
    search_fields = ["name"]
    form_fields = ["parent", "name"]
    list_display = ["name", "parent"]
    add_to_admin_menu = True


class TopicPairsViewSet(ModelViewSet):
    """Wagtail ModelViewSet for CourseTopic"""

    model = TopicsPair
    icon = "desktop"
    form_fields = ["parent_topic", "child_topic"]
    list_display = ["parent_topic", "parent_topic"]
    add_to_admin_menu = True
