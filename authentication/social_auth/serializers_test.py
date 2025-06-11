"""Serializers tests"""

import pytest
from rest_framework.exceptions import ValidationError
from social_core.backends.email import EmailAuth
from social_core.exceptions import AuthException, InvalidEmail

from authentication.social_auth.serializers import (
    LoginEmailSerializer,
    RegisterEmailSerializer,
)
from authentication.utils import SocialAuthState
from users.factories import UserFactory, UserSocialAuthFactory

EMAIL = "email@example.com"
TOKEN = {"token": "value"}

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "side_effect,result",  # noqa: PT006
    (  # noqa: PT007
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
        "authentication.social_auth.serializers.SocialAuthSerializer._authenticate"
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
    assert serializer.is_valid() is True, f"Received errors: {serializer.errors}"
    assert isinstance(serializer.save(), SocialAuthState)
    assert serializer.data == RegisterEmailSerializer(result).data


@pytest.mark.parametrize(
    "data,raises,message",  # noqa: PT006
    (  # noqa: PT007
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
    "is_active, force_caps,",  # noqa: PT006
    (  # noqa: PT007
        [True, True],  # noqa: PT007
        [True, False],  # noqa: PT007
        [False, True],  # noqa: PT007
    ),
)
def test_login_email_validation(mocker, is_active, force_caps):
    """Tests class-level validation of LoginEmailSerializer"""

    mocked_authenticate = mocker.patch(  # noqa: F841
        "authentication.social_auth.serializers.SocialAuthSerializer._authenticate"
    )

    user = UserFactory.create(is_active=is_active)

    # If force_caps, we want to make sure the flow works even if the user
    # specifies their email using capitalization that we don't have stored. So,
    # force the user lower and then re-force it upper for the rest of the test.

    if force_caps:
        user.email = user.email.lower()
        user.save()
        user.email = user.email.upper()

    user_social_auth = UserSocialAuthFactory.create(  # noqa: F841
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
    assert serializer.is_valid() is True, f"Received errors: {serializer.errors}"

    if is_active:
        assert len(LoginEmailSerializer(result).data["field_errors"]) == 0
    else:
        assert LoginEmailSerializer(result).data["field_errors"] == {
            "email": "Couldn't find your account"
        }


def test_login_email_validation_email_changed(mocker):
    """Tests class-level validation of LoginEmailSerializer for a user who changed their email address."""
    # No social auth record exists for the user after they have updated their email address

    mocked_authenticate = mocker.patch(  # noqa: F841
        "authentication.social_auth.serializers.SocialAuthSerializer._authenticate"
    )

    user = UserFactory.create()

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
    assert serializer.is_valid() is True, f"Received errors: {serializer.errors}"

    assert len(LoginEmailSerializer(result).data["field_errors"]) == 0


def test_login_email_validation_email_different_case(mocker):
    """Tests class-level validation of LoginEmailSerializer to handle different case of email entry."""

    mocked_authenticate = mocker.patch(  # noqa: F841
        "authentication.social_auth.serializers.SocialAuthSerializer._authenticate"
    )

    user = UserFactory.create()

    result = SocialAuthState(
        SocialAuthState.STATE_LOGIN_PASSWORD, partial=mocker.Mock(), user=user
    )
    result.flow = SocialAuthState.FLOW_LOGIN
    result.provider = EmailAuth.name
    serializer = LoginEmailSerializer(
        data={"flow": result.flow, "email": user.email.upper()},
        context={
            "backend": mocker.Mock(),
            "strategy": mocker.Mock(),
            "request": mocker.Mock(),
        },
    )
    assert serializer.is_valid() is True, f"Received errors: {serializer.errors}"

    assert len(LoginEmailSerializer(result).data["field_errors"]) == 0
