"""Serializers tests"""
import pytest
from rest_framework.exceptions import ValidationError
from social_core.backends.email import EmailAuth
from social_core.exceptions import AuthException, InvalidEmail

from authentication.serializers import (
    LoginEmailSerializer,
    RegisterEmailSerializer,
)
from authentication.utils import SocialAuthState
from users.factories import UserFactory, UserSocialAuthFactory

EMAIL = "email@example.com"
TOKEN = {"token": "value"}

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "side_effect,result",
    (
        (
            AuthException(None, "message"),
            SocialAuthState(SocialAuthState.STATE_ERROR, errors=["message"]),
        ),
        (InvalidEmail(None), SocialAuthState(SocialAuthState.STATE_INVALID_EMAIL)),
    ),
)
def test_social_auth_serializer_error(mocker, side_effect, result):
    """Tests that an AuthException exception is converted correctly"""
    mocked_authenticate = mocker.patch(
        "authentication.serializers.SocialAuthSerializer._authenticate"
    )
    mocked_authenticate.side_effect = side_effect

    result.flow = SocialAuthState.FLOW_REGISTER
    result.provider = EmailAuth.name

    serializer = RegisterEmailSerializer(
        data={"flow": result.flow, "email": "user@localhost"},
        context={
            "backend": mocker.Mock(),
            "strategy": mocker.Mock(),
            "request": mocker.Mock(),
        },
    )
    assert serializer.is_valid() is True, "Received errors: {}".format(
        serializer.errors
    )
    assert isinstance(serializer.save(), SocialAuthState)
    assert serializer.data == RegisterEmailSerializer(result).data


@pytest.mark.parametrize(
    "data,raises,message",
    (
        (
            {"email": None, "partial": None},
            ValidationError,
            "One of 'partial' or 'email' is required",
        ),
        (
            {"email": EMAIL, "partial": TOKEN},
            ValidationError,
            "Pass only one of 'partial' or 'email'",
        ),
        ({"email": EMAIL, "partial": None}, None, None),
        ({"email": None, "partial": TOKEN}, None, None),
    ),
)
def test_register_email_validation(data, raises, message):
    """Tests class-level validation of RegisterEmailSerializer"""
    if raises:
        with pytest.raises(raises) as exc:
            RegisterEmailSerializer().validate(data)
        assert exc.value.detail == [message]
    else:  # no exception
        assert RegisterEmailSerializer().validate(data) == data


@pytest.mark.parametrize(
    "is_active",
    (
        True,
        False,
    ),
)
def test_login_email_validation(mocker, is_active):
    """Tests class-level validation of LoginEmailSerializer"""

    mocked_authenticate = mocker.patch(
        "authentication.serializers.SocialAuthSerializer._authenticate"
    )

    user = UserFactory.create(is_active=is_active)
    user_social_auth = UserSocialAuthFactory.create(
        uid=user.email, provider=EmailAuth.name, user=user
    )

    if not is_active:
        result = SocialAuthState(
            SocialAuthState.STATE_REGISTER_REQUIRED,
            field_errors={"email": "Couldn't find your account"},
        )
    else:  # no exception
        result = SocialAuthState(
            SocialAuthState.STATE_LOGIN_PASSWORD, partial=mocker.Mock(), user=user
        )
    result.flow = SocialAuthState.FLOW_LOGIN
    result.provider = EmailAuth.name
    serializer = LoginEmailSerializer(
        data={"flow": result.flow, "email": user.email},
        context={
            "backend": mocker.Mock(),
            "strategy": mocker.Mock(),
            "request": mocker.Mock(),
        },
    )
    assert serializer.is_valid() is True, "Received errors: {}".format(
        serializer.errors
    )

    if is_active:
        assert len(LoginEmailSerializer(result).data["field_errors"]) == 0
    else:
        assert LoginEmailSerializer(result).data["field_errors"] == {
            "email": "Couldn't find your account"
        }
