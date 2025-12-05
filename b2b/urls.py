"""URL routing for the B2B API."""

from django.urls import include, path

import b2b.views.v0.urls as urls_v0

urlpatterns = [
    path("api/v0/b2b/", include((urls_v0, "v0"))),
]
