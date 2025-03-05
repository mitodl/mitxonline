"""Authentication views"""

from urllib.parse import quote, urlencode, urljoin, urlparse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render, reverse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from social_core.backends.email import EmailAuth
from social_django.models import UserSocialAuth
from social_django.utils import load_backend, load_strategy

from authentication.backends.ol_open_id_connect import OlOpenIdConnectAuth
from authentication.serializers import (
    LoginEmailSerializer,
    LoginPasswordSerializer,
    RegisterConfirmSerializer,
    RegisterDetailsSerializer,
    RegisterEmailSerializer,
    RegisterExtraDetailsSerializer,
)
from authentication.utils import load_drf_strategy
from main.constants import (
    USER_MSG_COOKIE_MAX_AGE,
    USER_MSG_COOKIE_NAME,
    USER_MSG_TYPE_COMPLETED_AUTH,
)
from main.utils import encode_json_cookie_value, is_success_response

User = get_user_model()


class SocialAuthAPIView(APIView):
    """API view for social auth endpoints"""

    authentication_classes = []
    permission_classes = []

    def get_serializer_cls(self):  # pragma: no cover
        """Return the serializer cls"""
        raise NotImplementedError("get_serializer_cls must be implemented")  # noqa: EM101

    def post(self, request):
        """Processes a request"""
        if bool(request.session.get("hijack_history")):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer_cls = self.get_serializer_cls()
        strategy = load_drf_strategy(request)
        backend = load_backend(strategy, EmailAuth.name, None)
        serializer = serializer_cls(
            data=request.data,
            context={"request": request, "strategy": strategy, "backend": backend},
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginEmailView(SocialAuthAPIView):
    """Email login view"""

    def get_serializer_cls(self):
        """Return the serializer cls"""
        return LoginEmailSerializer


class LoginPasswordView(SocialAuthAPIView):
    """Email login view"""

    def get_serializer_cls(self):
        """Return the serializer cls"""
        return LoginPasswordSerializer


@extend_schema(
    request=RegisterEmailSerializer,
    responses={200: RegisterEmailSerializer},
)
class RegisterEmailView(SocialAuthAPIView):
    """Email register view"""

    def get_serializer_cls(self):
        """Return the serializer cls"""
        return RegisterEmailSerializer

    def post(self, request):
        """Verify recaptcha response before proceeding"""
        if bool(request.session.get("hijack_history")):
            return Response(status=status.HTTP_403_FORBIDDEN)
        if settings.RECAPTCHA_SITE_KEY:
            r = requests.post(  # noqa: S113
                "https://www.google.com/recaptcha/api/siteverify?secret={key}&response={captcha}".format(
                    key=quote(settings.RECAPTCHA_SECRET_KEY),
                    captcha=quote(request.data["recaptcha"]),
                )
            )
            response = r.json()
            if not response["success"]:
                return Response(response, status=status.HTTP_400_BAD_REQUEST)
        return super().post(request)


class RegisterConfirmView(SocialAuthAPIView, GenericAPIView):
    """Email registration confirmation view"""

    serializer_class = RegisterConfirmSerializer
    permission_classes = []
    authentication_classes = []

    def get_serializer_cls(self):
        """Return the serializer class"""
        return RegisterConfirmSerializer

    def post(self, request):
        """
        Handle POST requests to confirm email registration
        """
        if bool(request.session.get("hijack_history")):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer_cls = self.get_serializer_cls()
        strategy = load_drf_strategy(request)
        backend = load_backend(strategy, EmailAuth.name, None)
        serializer = serializer_cls(
            data=request.data,
            context={"request": request, "strategy": strategy, "backend": backend},
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=RegisterDetailsSerializer,
    responses={200: RegisterDetailsSerializer},
)
class RegisterDetailsView(SocialAuthAPIView):
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
                        "type": USER_MSG_TYPE_COMPLETED_AUTH,
                    }
                ),
                max_age=USER_MSG_COOKIE_MAX_AGE,
            )
        return resp


@extend_schema(
    request=RegisterExtraDetailsSerializer,
    responses={200: RegisterExtraDetailsSerializer},
)
class RegisterExtraDetailsView(SocialAuthAPIView):
    """Email registration extra details view"""

    def get_serializer_cls(self):
        """Return the serializer cls"""
        return RegisterExtraDetailsSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_social_auth_types(request):
    """
    View that returns a serialized list of the logged-in user's UserSocialAuth types
    """
    social_auths = (
        UserSocialAuth.objects.filter(user=request.user).values("provider").distinct()
    )
    return Response(data=social_auths, status=status.HTTP_200_OK)


def confirmation_sent(request, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG001
    """The confirmation of an email being sent"""
    return render(request, "confirmation_sent.html")


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
            return False

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
