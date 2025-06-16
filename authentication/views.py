"""Authentication views"""

from urllib.parse import urlencode, urljoin, urlparse

from django.conf import settings
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import reverse
from django.views.generic.base import RedirectView
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


class LogoutView(DjangoLogoutView):
    """Custom view to modify base functionality in django.contrib.auth.views.LogoutView"""

    def get_next_page(self):
        next_page = super().get_next_page()

        if next_page in (self.next_page, self.request.path):
            return next_page
        else:
            params = {"redirect_url": settings.SITE_BASE_URL}
            next_page += ("&" if urlparse(next_page).query else "?") + urlencode(params)
            return next_page


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
            # so we redirect into the Api
            if self.request.user.is_authenticated:
                # we use the /logout/done
                qs = {
                    "post_logout_redirect_uri": urljoin(
                        settings.SITE_BASE_URL, "/logout/done"
                    )
                }

                return urljoin(settings.SITE_BASE_URL, f"/logout/oidc?{urlencode(qs)}")
            return settings.SITE_BASE_URL
        else:
            # Otherwise we need to send them to openedx first
            params = {"redirect_url": settings.SITE_BASE_URL}
            return f"{settings.LOGOUT_REDIRECT_URL}?{urlencode(params)}"


@api_view(["GET"])
@renderer_classes([JSONRenderer])
@permission_classes([])
def logout_complete(request):  # noqa: ARG001
    """Simple response for openedx logout being complete"""
    return Response({"message": "Logout complete"}, content_type="application/json")


@api_view(["GET"])
@renderer_classes([JSONRenderer])
@permission_classes([])
def well_known_openid_configuration(request):  # noqa: ARG001
    """View for openid configuration"""
    # See: https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfig
    # NOTE: this is intentionally incomplete because we don't fully support OpenID
    #       this was implemented solely for digital credentials
    return Response(
        {
            "issuer": settings.SITE_BASE_URL,
            "authorization_endpoint": urljoin(
                settings.SITE_BASE_URL, reverse("oauth2_provider:authorize")
            ),
            "token_endpoint": urljoin(
                settings.SITE_BASE_URL, reverse("oauth2_provider:token")
            ),
        },
        content_type="application/json",
    )
