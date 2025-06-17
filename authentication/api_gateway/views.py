"""Authentication views"""

from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
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

User = get_user_model()


class ProfileDetailsAPIView(APIView):
    """API view for profile update endpoints"""

    authentication_classes = (SessionAuthentication, TokenAuthentication)
    permission_classes = [IsAuthenticated]

    def get_serializer_cls(self):  # pragma: no cover
        """Return the serializer cls"""
        raise NotImplementedError("get_serializer_cls must be implemented")  # noqa: EM101

    def post(self, request):
        """Processes a request"""
        if bool(request.session.get("hijack_history")):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer_cls = self.get_serializer_cls()
        serializer = serializer_cls(
            data=request.data,
            context={"request": request},
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=RegisterDetailsSerializer,
    responses={200: RegisterDetailsSerializer},
)
class RegisterDetailsView(ProfileDetailsAPIView):
    """Email registration details view"""

    def get_serializer_cls(self):
        """Return the serializer cls"""
        return RegisterDetailsSerializer

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


@extend_schema(
    request=RegisterExtraDetailsSerializer,
    responses={200: RegisterExtraDetailsSerializer},
)
class RegisterExtraDetailsView(ProfileDetailsAPIView):
    """Extra profile details view"""

    def get_serializer_cls(self):
        """Return the serializer cls"""
        return RegisterExtraDetailsSerializer


def get_redirect_url(request):
    """
    Get the redirect URL from the request.

    Args:
        request: Django request object

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
        else "/dashboard"
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
        if not request.user.is_anonymous:
            profile = request.user.user_profile
            if (
                not profile.completed_onboarding
                and request.GET.get("skip_onboarding", "0") == "0"
            ):
                params = urlencode({"next": redirect_url})
                redirect_url = f"{settings.MITXONLINE_NEW_USER_LOGIN_URL}?{params}"
                profile.completed_onboarding = True
                profile.save()
        return redirect(redirect_url)


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
