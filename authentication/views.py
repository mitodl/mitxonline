"""Authentication views"""

from urllib.parse import urljoin

from django.conf import settings
from django.shortcuts import reverse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


@api_view(["GET"])
@renderer_classes([JSONRenderer])
@permission_classes([])
def well_known_openid_configuration(request):  # noqa: ARG001
    """View for openid configuration"""
    # See: https://openid.net/specs/openid-connect-discovery-1_0.html#ProviderConfig
    # NOTE: this is intentionally incomplete because we don't fully support OpenID
    #       this was implemented solely for digital credentials

    # In dev, we need to use host.docker.internal to reach the token & userinfo endpoint
    token_base_url = settings.SITE_BASE_URL
    if settings.ENVIRONMENT == "dev":
        token_base_url = "http://host.docker.internal:9080"

    return Response(
        {
            "issuer": settings.SITE_BASE_URL,
            "authorization_endpoint": urljoin(
                settings.SITE_BASE_URL, reverse("oauth2_provider:authorize")
            ),
            "token_endpoint": urljoin(token_base_url, reverse("oauth2_provider:token")),
            "userinfo_endpoint": urljoin(token_base_url, reverse("userinfo_api")),
        },
        content_type="application/json",
    )
