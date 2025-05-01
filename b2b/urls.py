"""URL routing for the B2B API."""

from django.urls import include, re_path

import b2b.views.v0.urls as urls_v0

urlpatterns = [
    re_path(r"^api/v0/b2b/", include((urls_v0, "v0"))),
]
