"""Course API URL routes"""
from django.urls import include, path, re_path

import courses.urls.v1.urls as urls_v1
import courses.urls.v2.urls as urls_v2

from courses.views import v1

urlpatterns = [
    path("enrollments/", v1.create_enrollment_view, name="create-enrollment-via-form"),
]

urlpatterns += [
    re_path("^api/", include(urls_v1, "v1")),
    re_path("^api/v1/", include(urls_v1, "v1")),
    re_path("^api/v2/", include(urls_v2, "v2")),
]
