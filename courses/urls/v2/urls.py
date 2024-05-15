from rest_framework import routers

from courses.views import v2

app_name = "courses"
router = routers.SimpleRouter()
router.register(r"programs", v2.ProgramViewSet, basename="programs_api")
router.register(r"courses", v2.CourseViewSet, basename="courses_api")
router.register(r"departments", v2.DepartmentViewSet, basename="departments_api")
router.register(
    r"parent_course_topics", v2.CourseTopicViewSet, basename="parent_course_topics_api"
)

urlpatterns = router.urls
