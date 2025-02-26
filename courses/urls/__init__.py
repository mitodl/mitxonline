"""Course API URL routes"""

from django.urls import include, path
from rest_framework import routers

import courses.urls.v1.urls as urls_v1
import courses.urls.v2.urls as urls_v2
from courses.views import v1

router = routers.SimpleRouter()


urlpatterns = [
    path("api/", include(urls_v1, "v1")),
    path("api/v1/", include(urls_v1, "v1")),
    path("api/v2/", include(urls_v2, "v2")),
]

urlpatterns += [
    path("api/records/program/<int:pk>/share/", v1.get_learner_record_share),
    path("api/records/program/<int:pk>/revoke/", v1.revoke_learner_record_share),
    path("api/records/program/<int:pk>/", v1.get_learner_record),
    path(
        "api/records/shared/<uuid>/",
        v1.get_learner_record_from_uuid,
        name="shared_learner_record_from_uuid",
    ),
]

urlpatterns += [
    path("enrollments/", v1.create_enrollment_view, name="create-enrollment-via-form"),
]
