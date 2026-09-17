"""Authentication views"""

import logging
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic.base import RedirectView
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.api_gateway.serializers import (
    RegisterDetailsSerializer,
    RegisterExtraDetailsSerializer,
)
from main.constants import (
    USER_MSG_COOKIE_MAX_AGE,
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_PROFILE_CREATED,
)
from main.utils import encode_json_cookie_value, is_success_response
from users.models import UserProfile

User = get_user_model()

log = logging.getLogger()


class ProfileDetailsAPIView(APIView):
    """API view for profile update endpoints"""

    serializer_class = None
    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = [IsAuthenticated]

    def get_serializer_cls(self):  # pragma: no cover
        """Return the serializer cls"""
        if self.serializer_class is None:
            raise NotImplementedError("get_serializer_cls must be implemented")  # noqa: EM101
        return self.serializer_class

    @extend_schema(exclude=True)
    def post(self, request):
        """Processes a request"""
        serializer_cls = self.get_serializer_cls()
        serializer = serializer_cls(
            data=request.data,
            context={"request": request},
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterDetailsView(ProfileDetailsAPIView):
    """Email registration details view"""

    serializer_class = RegisterDetailsSerializer

    @extend_schema(exclude=True)
    def post(self, request):
        resp = super().post(request)
        if is_success_response(resp):
            resp.set_cookie(
                key=USER_MSG_COOKIE_NAME,
                value=encode_json_cookie_value(
                    {
                        "type": USER_MSG_TYPE_PROFILE_CREATED,
                    }
                ),
                max_age=USER_MSG_COOKIE_MAX_AGE,
            )
        return resp


class RegisterExtraDetailsView(ProfileDetailsAPIView):
    """Extra profile details view"""

    serializer_class = RegisterExtraDetailsSerializer


def get_redirect_url(request, default="/dashboard"):
    """
    Get the redirect URL from the request.

    Args:
        request: Django request object
        default: Where to send the user when no usable `next` was supplied

    Returns:
        str: Redirect URL
    """
    next_url = request.GET.get("next") or request.COOKIES.get("next")
    return (
        next_url
        if next_url
        and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts=settings.ALLOWED_REDIRECT_HOSTS
        )
        else default
    )


class GatewayLoginView(View):
    """
    Redirect the user to the appropriate url after login
    """

    def get(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):
        """
        GET endpoint for logging a user in.
        """
        redirect_url = get_redirect_url(request)
        user = request.user
        if (
            not user.is_anonymous
            and not user.should_skip_onboarding
            and request.GET.get("skip_onboarding", "0") == "0"
        ):
            params = urlencode({"next": redirect_url})
            redirect_url = f"{settings.MITXONLINE_NEW_USER_LOGIN_URL}?{params}"

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.completed_onboarding = True
            profile.save()
        return redirect(redirect_url)


class SwitchSessionView(RedirectView):
    """
    Discard whatever session this browser arrived with, then continue to `next`.

    Entry point for hand-offs from MIT Learn (hq#12763).  Learn and MITx Online
    sit behind separate APISIX gateway sessions on separate parent domains, so a
    browser that switched users on Learn can still be carrying the *previous*
    user's MITx Online session -- and the gateway will happily assert that
    identity to us for as long as its cached access token has left to run.

    The APISIX route for this path carries no ``openid-connect`` plugin and
    instead expires the gateway session cookie on the way out, so the redirect
    below lands on a route that has to authenticate from scratch and comes back
    as whoever currently holds the Keycloak SSO session.  Django's own session
    is dropped here for the same reason: on its own it would keep naming the
    previous user.

    Deliberately not a logout: Keycloak is never contacted, because ending the
    SSO session would log the user out of Learn as well -- the opposite of what
    a hand-off from Learn wants.
    """

    permanent = False

    def get(self, request, *args, **kwargs):
        """Drop Django's session, then redirect.

        The session is dropped here rather than in ``get_redirect_url`` so that
        a HEAD request, which also resolves the redirect target, does not carry
        the side effect.
        """
        if request.user.is_authenticated:
            logout(request)
        return super().get(request, *args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        """Return the URL to continue to once the session has been dropped."""
        target = get_redirect_url(self.request, default="/cart/")

        # Carry any other query parameters through to the destination -- notably
        # `ecom-service`, which Learn sets to suppress MITx Online's own chrome.
        passthrough = {
            key: value for key, value in self.request.GET.items() if key != "next"
        }
        if not passthrough:
            return target

        scheme, netloc, path, query, fragment = urlsplit(target)
        merged = urlencode(
            {**dict(parse_qsl(query)), **passthrough},
        )
        return urlunsplit((scheme, netloc, path, merged, fragment))


class OpenedxAndApiGatewayLogoutView(RedirectView):
    """
    Custom view to support logout under APISIX

    The logical flow is:
    - http://mitxonline/logout
      - if `?no_redirect=1` is not passed:
        - redirect to http://openedx/logout?redirect_url=http://mitxonline/
          - this page makes iframe requests to http://mitxonline/logout?no_redirect=1
      - if `?no_redirect=1` is passed:
        - redirect to http://mitxonline/logout/oidc
    """

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        no_redirect = self.request.GET.get("no_redirect")

        if no_redirect and no_redirect[0] == "1":
            # This is openedx's /logout interstitial page calling us in an iframe
            # so we redirect into the API gatewat logout but ONLY if the user is authenticated
            if self.request.user.is_authenticated:
                return urljoin(settings.SITE_BASE_URL, "/logout/oidc")
            return settings.SITE_BASE_URL
        else:
            # Otherwise we need to send them to openedx first
            params = {"redirect_url": settings.SITE_BASE_URL}
            return f"{settings.LOGOUT_REDIRECT_URL}?{urlencode(params)}"


@extend_schema(exclude=True)
@api_view(["GET"])
@renderer_classes([JSONRenderer])
@permission_classes([])
def logout_complete(request):  # noqa: ARG001
    """Simple response for openedx logout being complete"""
    return Response({"message": "Logout complete"}, content_type="application/json")


class AccountActionStartView(RedirectView):
    """View that redirect the user to keycloak based on the requested action"""

    ACTION_MAPPING: dict[str, str] = {
        "update-email": "UPDATE_EMAIL",
        "update-password": "UPDATE_PASSWORD",
    }

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        """Get the redirect url"""

        action = kwargs["action"]

        if action not in self.ACTION_MAPPING:
            log.error("Received unexpected account action: %s", action)
            redirect_url = self.request.headers.get("referer", settings.SITE_BASE_URL)
            return (
                redirect_url
                if url_has_allowed_host_and_scheme(
                    redirect_url, allowed_hosts=settings.ALLOWED_REDIRECT_HOSTS
                )
                else settings.SITE_BASE_URL
            )

        next_url = get_redirect_url(self.request)

        callback_qs = {
            "next": next_url,
        }
        callback_url = f"{settings.SITE_BASE_URL.removesuffix('/')}{reverse('account-action-complete')}?{urlencode(callback_qs)}"

        qs = {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": callback_url,
            "scope": "openid",
            "kc_action": self.ACTION_MAPPING[action],
        }

        return "".join(
            [
                settings.KEYCLOAK_BASE_URL.removesuffix("/"),
                "/realms/",
                settings.KEYCLOAK_REALM_NAME,
                "/protocol/openid-connect/auth?",
                urlencode(qs),
            ]
        )


class AccountActionCallbackView(RedirectView):
    """Callback for the account action flow"""

    def get_redirect_url(self, *args, **kwargs):  # noqa: ARG002
        """Get the redirect url"""
        return get_redirect_url(self.request)
