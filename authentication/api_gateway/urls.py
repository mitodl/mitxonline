"""URL configurations for authentication"""

from django.urls import path, re_path

from authentication.api_gateway.views import (
    GatewayLoginView,
    OpenedxAndApiGatewayLogoutView,
    RegisterDetailsView,
    RegisterExtraDetailsView,
    logout_complete,
)

urlpatterns = [
    path(
        "api/profile/details/",
        RegisterDetailsView.as_view(),
        name="profile-details-api",
    ),
    path(
        "api/profile/extra/",
        RegisterExtraDetailsView.as_view(),
        name="profile-extra-api",
    ),
    path(r"login/", GatewayLoginView.as_view(), name="gateway-login"),
    re_path(
        r"^logout\/?$",
        OpenedxAndApiGatewayLogoutView.as_view(),
        name="logout",
    ),
    path("logout/complete", logout_complete, name="logout-complete"),
    # NOTE: APISIX handles the logout/oidc route
]
