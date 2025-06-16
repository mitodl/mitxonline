"""URL configurations for authentication"""

from django.conf import settings
from django.urls import path, re_path
from django.urls.conf import include

from authentication.views import (
    LogoutView,
    OpenedxAndApiGatewayLogoutView,
    logout_complete,
    well_known_openid_configuration,
)

urlpatterns = [
    path("", include("authentication.social_auth.urls")),
    path("", include("authentication.api_gateway.urls")),
    re_path(
        r"^logout\/?$",
        (
            LogoutView.as_view()
            if settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE
            else OpenedxAndApiGatewayLogoutView.as_view()
        ),
        name="logout",
    ),
    path("logout/complete", logout_complete, name="logout-complete"),
    # NOTE: APISIX handles the logout/oidc route
    path(
        ".well-known/openid-configuration",
        well_known_openid_configuration,
        name="well-known-openid-configuration",
    ),
]
