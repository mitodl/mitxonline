"""Course API URL routes"""

from django.urls import path
from rest_framework import routers

from courses.views import v1

router = routers.SimpleRouter()


urlpatterns = [
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
