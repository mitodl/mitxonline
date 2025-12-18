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

urlpatterns = [
    *router.urls,
    path(
        r"course_certificates/<str:cert_uuid>/",
        v2.get_course_certificate,
        name="get_course_certificate",
    ),
    path(
        r"program_certificates/<str:cert_uuid>/",
        v2.get_program_certificate,
        name="get_program_certificate",
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
# http://mitxonline.odl.local:8013/api/v2/courses/course_certificates/cc7dfe00-44b4-4ff2-9369-5cf3fbd74cf6/
# http://mitxonline.odl.local:8013/api/v2/course_certificates/cc7dfe00-44b4-4ff2-9369-5cf3fbd74cf6/
