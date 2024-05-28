"""Wagtail admin views"""

from wagtail.admin.viewsets.model import ModelViewSet

from courses.models import CoursesTopic


class CourseTopicViewSet(ModelViewSet):
    """Wagtail ModelViewSet for CourseTopic"""

    model = CoursesTopic
    icon = "desktop"
    search_fields = ["name"]
    form_fields = ["parent", "name"]
    list_display = ["name", "parent"]
    add_to_admin_menu = True
