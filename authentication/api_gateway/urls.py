"""URL configurations for authentication"""

from django.urls import path, re_path

from authentication.api_gateway.views import (
    AccountActionCallbackView,
    AccountActionStartView,
    GatewayLoginView,
    OpenedxAndApiGatewayLogoutView,
    RegisterDetailsView,
    RegisterExtraDetailsView,
    SwitchSessionView,
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
    path("login/", GatewayLoginView.as_view(), name="gateway-login"),
    # Gateway session reset for hand-offs from MIT Learn.  The APISIX route for
    # this path expires the gateway session cookie; this view drops Django's and
    # forwards to `next`.
    re_path(
        r"^switch-session\/?$",
        SwitchSessionView.as_view(),
        name="switch-session",
    ),
    re_path(
        r"^logout\/?$",
        OpenedxAndApiGatewayLogoutView.as_view(),
        name="logout",
    ),
    path("logout/complete", logout_complete, name="logout-complete"),
    # NOTE: APISIX handles the logout/oidc route
    path(
        "account/action/start/<slug:action>/",
        AccountActionStartView.as_view(),
        name="account-action-start",
    ),
    path(
        "account/action/complete",
        AccountActionCallbackView.as_view(),
        name="account-action-complete",
    ),
]
