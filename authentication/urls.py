"""URL configurations for authentication"""

from django.conf import settings
from django.urls import path
from django.urls.conf import include

from authentication.views import (
    well_known_openid_configuration,
)

urlpatterns = [
    (
        path("", include("authentication.social_auth.urls"))
        if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE
        else path("", include("authentication.api_gateway.urls"))
    ),
    path(
        ".well-known/openid-configuration",
        well_known_openid_configuration,
        name="well-known-openid-configuration",
    ),
]
