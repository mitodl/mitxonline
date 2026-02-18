"""Course API v3 URL configuration."""

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

urlpatterns = router.urls
