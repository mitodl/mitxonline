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
    path('learner-record-share/<int:pk>/', v1.LearnerRecordShareView.as_view(), name='learner-record-share'),
    path('revoke-learner-record-share/<int:pk>/', v1.RevokeLearnerRecordShareView.as_view(), name='revoke-learner-record-share'),
    path('learner-record/<int:pk>/', v1.GetLearnerRecordView.as_view(), name='get-learner-record'),
    path('learner-record/<uuid:uuid>/', v1.LearnerRecordFromUUIDView.as_view(), name="shared_learner_record_from_uuid")
]

urlpatterns += [
    path('enrollments/', v1.CreateEnrollmentView.as_view(), name='create-enrollment-via-form'),
]
