"""URL configurations for authentication"""

from django.urls import path

from authentication.api_gateway.views import (
    GatewayLoginView,
    RegisterDetailsView,
    RegisterExtraDetailsView,
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
]
