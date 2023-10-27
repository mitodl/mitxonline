from rest_framework import routers

from courses.views import v2

router = routers.SimpleRouter()
router.register(r"programs", v2.ProgramViewSet, basename="programs_api")

