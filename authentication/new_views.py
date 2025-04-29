"""Authentication views"""

from urllib.parse import urlencode, urljoin, urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from social_django.utils import load_strategy

from authentication.backends.ol_open_id_connect import OlOpenIdConnectAuth
from authentication.new_serializers import (
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
        else "/app"
    )


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


class CustomLogoutView(LogoutView):
    """Custom view to modify base functionality in django.contrib.auth.views.LogoutView"""

    def _keycloak_logout_url(self, user):
        """
        Return the OpenID Connect logout URL for a user based on
        their SocialAuth record's id_token and the currently
        configured Keycloak environment variables.

        Args:
            user (User): User model record associated with the SocialAuth record.

        Returns:
            string: The URL to redirect the user to in order to logout.
        """
        strategy = load_strategy()
        storage = strategy.storage
        user_social_auth_record = storage.user.get_social_auth_for_user(
            user, provider=OlOpenIdConnectAuth.name
        ).first()

        if not user_social_auth_record:
            return None

        id_token = user_social_auth_record.extra_data.get("id_token")
        qs = urlencode(
            {
                "id_token_hint": id_token,
                "post_logout_redirect_uri": self.request.build_absolute_uri(
                    settings.LOGOUT_REDIRECT_URL
                ),
            }
        )

        return (
            f"{settings.KEYCLOAK_BASE_URL}/realms/"
            f"{settings.KEYCLOAK_REALM_NAME}/protocol/openid-connect/logout"
            f"?{qs}"
        )

    def get_next_page(self):
        next_page = super().get_next_page()

        if next_page in (self.next_page, self.request.path):
            return next_page
        else:
            params = {"redirect_url": settings.SITE_BASE_URL}
            next_page += ("&" if urlparse(next_page).query else "?") + urlencode(params)
            return next_page

    def get(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):
        """
        GET endpoint for logging a user out.

        The logout redirect path the user follows is:

        - api.example.com/logout (this view)
        - keycloak.example.com/realms/REALM/protocol/openid-connect/logout
        - api.example.com/app (see main/urls.py)
        - app.example.com

        """
        user = getattr(request, "user", None)
        keycloak_redirect = self._keycloak_logout_url(user)

        if not keycloak_redirect:
            return super().get(request)

        if user and user.is_authenticated:
            super().get(request)
            return redirect(keycloak_redirect)
        else:
            return redirect(settings.LOGOUT_REDIRECT_URL)


class CustomLoginView(LoginView):
    """
    Log in the user
    """

    def get(
        self,
        request,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ):
        """
        GET
        endpoint
        for logging a user in.
        """
        return redirect(get_redirect_url(request))


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
