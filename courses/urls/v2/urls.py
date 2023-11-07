from django.urls import include, re_path
from rest_framework import routers

from courses.views import v2

app_name = "courses"
router = routers.SimpleRouter()
router.register(r"programs", v2.ProgramViewSet, basename="programs_api")
router.register(r"courses", v2.CourseViewSet, basename="courses_api")

urlpatterns = router.urls
