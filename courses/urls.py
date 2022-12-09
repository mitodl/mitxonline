"""Course API URL routes"""
from django.urls import include, path, re_path
from rest_framework import routers

from courses.views import v1

router = routers.SimpleRouter()
router.register(r"programs", v1.ProgramViewSet, basename="programs_api")
router.register(r"courses", v1.CourseViewSet, basename="courses_api")
router.register(r"course_runs", v1.CourseRunViewSet, basename="course_runs_api")
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

urlpatterns = [
    re_path(r"^api/v1/", include(router.urls)),
    re_path(r"^api/", include(router.urls)),
    path("api/records/program/<pk>/share/", v1.get_learner_record_share),
    path("api/records/program/<pk>/revoke/", v1.revoke_learner_record_share),
    path("api/records/program/<pk>/", v1.get_learner_record),
    path(
        "api/records/shared/<uuid>/",
        v1.get_learner_record_from_uuid,
        name="shared_learner_record_from_uuid",
    ),
    path("enrollments/", v1.create_enrollment_view, name="create-enrollment-via-form"),
]
