from rest_framework import routers

from courses.views import v1

app_name = "courses"

router = routers.SimpleRouter()
router.register(r"programs", v1.ProgramViewSet, basename="programs_api")
router.register(r"courses", v1.CourseViewSet, basename="courses_api")
router.register(r"course_runs", v1.CourseRunViewSet, basename="course_runs_api")
router.register(r"departments", v1.DepartmentViewSet, basename="departments_api")
router.register(
    r"enrollments", v1.UserEnrollmentsApiViewSet, basename="user-enrollments-api"
)
router.register(
    r"partnerschools", v1.PartnerSchoolViewSet, basename="partner_schools_api"
)
router.register(
    r"program_enrollments",
    v1.UserProgramEnrollmentsViewSet,
    basename="user_program_enrollments_api",
)

urlpatterns = router.urls
