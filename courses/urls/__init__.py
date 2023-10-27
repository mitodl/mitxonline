"""Course API URL routes"""
from django.urls import include, path, re_path

from courses.urls.v1 import urls as urls_v1

from courses.urls.v2 import urls as urls_v2

from courses.views import v1


urlpatterns = [
    re_path(r"^api/v2/", include(urls_v2.router.urls)),
    re_path(r"^api/v1/", include(urls_v1.router.urls)),
    re_path(r"^api/", include(urls_v1.router.urls)),
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
