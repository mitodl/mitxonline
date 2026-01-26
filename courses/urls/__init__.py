"""Course API URL routes"""

from django.urls import include, path

from courses.urls.v1 import urls as v1_urls
from courses.views import v1

urlpatterns = [
    # there is some circular import error somewhere that
    # we need to hunt down and fix preventing usage of a string include here
    path("api/v1/", include(v1_urls, "v1")),
    path("api/v2/", include("courses.urls.v2.urls", "v2")),
    path("api/v3/", include("courses.urls.v3.urls", "v3")),
    path(
        "api/records/program/<int:pk>/share/",
        v1.LearnerRecordShareView.as_view(),
        name="learner-record-share",
    ),
    path(
        "api/records/program/<int:pk>/revoke/",
        v1.RevokeLearnerRecordShareView.as_view(),
        name="revoke-learner-record-share",
    ),
    path(
        "api/records/program/<int:pk>/",
        v1.GetLearnerRecordView.as_view(),
        name="get-learner-record",
    ),
    path(
        "api/records/shared/<uuid:uuid>/",
        v1.LearnerRecordFromUUIDView.as_view(),
        name="shared_learner_record_from_uuid",
    ),
    path(
        "enrollments/",
        v1.CreateEnrollmentView.as_view(),
        name="create-enrollment-via-form",
    ),
]
