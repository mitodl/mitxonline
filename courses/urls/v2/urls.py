"""Course API v2 URL configuration."""

from django.urls import path
from rest_framework import routers

from courses.views import v2

app_name = "courses"
router = routers.SimpleRouter()
router.register(r"programs", v2.ProgramViewSet, basename="programs_api")
router.register(
    r"program-collections",
    v2.ProgramCollectionViewSet,
    basename="program_collections_api",
)
router.register(r"courses", v2.CourseViewSet, basename="courses_api")
router.register(r"departments", v2.DepartmentViewSet, basename="departments_api")
router.register(
    r"enrollments", v2.UserEnrollmentsApiViewSet, basename="user-enrollments-api"
)
router.register(
    r"program_enrollments",
    v2.UserProgramEnrollmentsViewSet,
    basename="user_program_enrollments_api",
)
router.register(
    r"course_certificates",
    v2.CourseCertificateRetrieveViewSet,
    basename="course_certificates_api",
)
router.register(
    r"program_certificates",
    v2.ProgramCertificateRetrieveViewSet,
    basename="program_certificates_api",
)

urlpatterns = [
    *router.urls,
    path(
        r"verified_program_enrollments/<str:courserun_id>/",
        v2.add_verified_program_course_enrollment,
        name="add_verified_program_course_enrollment",
    ),
    path(
        "verifiable_course_credential/<uuid:credential_id>/download/",
        v2.download_course_credential,
        name="download_course_credential",
    ),
    path(
        "verifiable_program_credential/<uuid:credential_id>/download/",
        v2.download_program_credential,
        name="download_program_credential",
    ),
]
