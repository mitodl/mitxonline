"""URL configurations for pytest"""

from django.urls import path
from django.urls.conf import include

urlpatterns = [
    path("", include("mitol.scim.urls")),
    path("", include("authentication.api_gateway.urls")),
]
