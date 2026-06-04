"""Course API v3 URL configuration."""

from django.urls import path
from rest_framework import routers

from courses.views import v3

app_name = "courses"

router = routers.SimpleRouter()
router.register(
    r"enrollments",
    v3.UserEnrollmentsApiViewSet,
    basename="user_enrollments_api",
)
router.register(
    r"program_enrollments",
    v3.UserProgramEnrollmentsViewSet,
    basename="user_program_enrollments_api",
)
router.register(
    r"courses/ingestible",
    v3.IngestibleCourseViewSet,
    basename="ingestible_courses_api",
)

urlpatterns = router.urls
urlpatterns += [
    path(
        "courses/<str:course_id>/ol_openedx_outline/",
        v3.get_course_outline,
        name="course_outline",
    ),
    path(
        "courses/variant_runs/",
        v3.get_course_variant_runs,
        name="course_variant_runs",
    ),
]
