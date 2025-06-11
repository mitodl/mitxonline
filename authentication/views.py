"""Authentication views"""

from urllib.parse import urlencode, urljoin, urlparse

from django.conf import settings
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.shortcuts import reverse
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
