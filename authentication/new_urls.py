"""URL configurations for authentication"""

from django.urls import path
from django.urls.conf import include

from authentication.new_views import (
    CustomLoginView,
    CustomLogoutView,
    RegisterDetailsView,
    RegisterExtraDetailsView,
    well_known_openid_configuration,
)

urlpatterns = [
    path("api/", include("mitol.authentication.urls.djoser_urls")),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path(r"login/", CustomLoginView.as_view(), name="gateway-login"),
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
    path(
        ".well-known/openid-configuration",
        well_known_openid_configuration,
        name="well-known-openid-configuration",
    ),
]
