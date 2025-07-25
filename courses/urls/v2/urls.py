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

urlpatterns = [
    *router.urls,
    path(r"course_certificates/<str:cert_uuid>/", v2.get_course_certificate),
    path(r"program_certificates/<str:cert_uuid>/", v2.get_program_certificate),
]
