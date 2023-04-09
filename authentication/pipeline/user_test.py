"""Tests of user pipeline actions"""
# pylint: disable=redefined-outer-name

import pytest
import responses
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError
from rest_framework import status
from social_core.backends.email import EmailAuth
from social_django.utils import load_backend, load_strategy

from authentication.exceptions import (
    EmailBlockedException,
    InvalidPasswordException,
    RequirePasswordAndPersonalInfoException,
    RequirePasswordException,
    RequireProfileException,
    RequireRegistrationException,
    UnexpectedExistingUserException,
    UserCreationFailedException,
)
from authentication.pipeline import user as user_actions
from authentication.utils import SocialAuthState
from openedx.api import OPENEDX_REGISTRATION_VALIDATION_PATH
from users.factories import UserFactory

User = get_user_model()


@pytest.fixture
def backend_settings(settings):
    """A dictionary of settings for the backend"""
    return {"USER_FIELDS": settings.SOCIAL_AUTH_EMAIL_USER_FIELDS}


@pytest.fixture
def mock_email_backend(mocker, backend_settings):
    """Fixture that returns a fake EmailAuth backend object"""
    backend = mocker.Mock()
    backend.name = "email"
    backend.setting.side_effect = lambda key, default, **kwargs: backend_settings.get(
        key, default
    )
    return backend


@pytest.fixture
def mock_create_user_strategy(mocker):
    """Fixture that returns a valid strategy for create_user_via_email"""
    strategy = mocker.Mock()
    strategy.request = mocker.Mock()
    strategy.request_data.return_value = {
        "name": "Jane Doe",
        "password": "password1",
        "username": "custom-username",
        "legal_address": {
            "first_name": "Jane",
            "last_name": "Doe",
            "country": "US",
            "state": "US-MA",
        },
    }
    return strategy


@pytest.fixture()
def application(settings):
    """Test data and settings needed for create_edx_user tests"""
    settings.OPENEDX_API_BASE_URL = "http://example.com"


def validate_email_auth_request_not_email_backend(mocker):
    """Tests that validate_email_auth_request return if not using the email backend"""
    mock_strategy = mocker.Mock()
    mock_backend = mocker.Mock()
    mock_backend.name = "notemail"
    assert user_actions.validate_email_auth_request(mock_strategy, mock_backend) == {}


@pytest.mark.parametrize(
    "has_user,expected", [(True, {"flow": SocialAuthState.FLOW_LOGIN}), (False, {})]
)
@pytest.mark.django_db
def test_validate_email_auth_request(rf, has_user, expected):
    """Test that validate_email_auth_request returns correctly given the input"""
    request = rf.post("/complete/email")
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()
    strategy = load_strategy(request)
    backend = load_backend(strategy, "email", None)

    user = UserFactory.create() if has_user else None

    assert (
        user_actions.validate_email_auth_request(
            strategy, backend, pipeline_index=0, user=user
        )
        == expected
    )


def test_get_username(mocker, user):
    """Tests that we get a username for a new user"""
    mock_strategy = mocker.Mock()
    mock_strategy.storage.user.get_username.return_value = user.username
    assert user_actions.get_username(mock_strategy, None, user) == {
        "username": user.username
    }
    mock_strategy.storage.user.get_username.assert_called_once_with(user)


def test_get_username_no_user(mocker):
    """Tests that get_username returns None if there is no User"""
    mock_strategy = mocker.Mock()
    assert user_actions.get_username(mock_strategy, None, None)["username"] is None
    mock_strategy.storage.user.get_username.assert_not_called()


def test_user_password_not_email_backend(mocker):
    """Tests that user_password return if not using the email backend"""
    mock_strategy = mocker.MagicMock()
    mock_user = mocker.Mock()
    mock_backend = mocker.Mock()
    mock_backend.name = "notemail"
    assert (
        user_actions.validate_password(
            mock_strategy,
            mock_backend,
            pipeline_index=0,
            user=mock_user,
            flow=SocialAuthState.FLOW_LOGIN,
        )
        == {}
    )
    # make sure we didn't update or check the password
    mock_user.set_password.assert_not_called()
    mock_user.save.assert_not_called()
    mock_user.check_password.assert_not_called()


@pytest.mark.parametrize("user_password", ["abc123", "def456"])
def test_user_password_login(rf, user, user_password):
    """Tests that user_password works for login case"""
    request_password = "abc123"
    user.set_password(user_password)
    user.save()
    request = rf.post(
        "/complete/email", {"password": request_password, "email": user.email}
    )
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()
    strategy = load_strategy(request)
    backend = load_backend(strategy, "email", None)

    if request_password == user_password:
        assert (
            user_actions.validate_password(
                strategy,
                backend,
                pipeline_index=0,
                user=user,
                flow=SocialAuthState.FLOW_LOGIN,
            )
            == {}
        )
    else:
        with pytest.raises(InvalidPasswordException):
            user_actions.validate_password(
                strategy,
                backend,
                pipeline_index=0,
                user=user,
                flow=SocialAuthState.FLOW_LOGIN,
            )


def test_user_password_not_login(rf, user):
    """
    Tests that user_password performs denies authentication
    for an existing user if password not provided regardless of auth_type
    """
    user.set_password("abc123")
    user.save()
    request = rf.post("/complete/email", {"email": user.email})
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()
    strategy = load_strategy(request)
    backend = load_backend(strategy, "email", None)

    with pytest.raises(RequirePasswordException):
        user_actions.validate_password(
            strategy,
            backend,
            pipeline_index=0,
            user=user,
            flow=SocialAuthState.FLOW_LOGIN,
        )


def test_user_password_not_exists(rf):
    """Tests that user_password raises auth error for nonexistent user"""
    request = rf.post(
        "/complete/email", {"password": "abc123", "email": "doesntexist@localhost"}
    )
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()
    strategy = load_strategy(request)
    backend = load_backend(strategy, "email", None)

    with pytest.raises(RequireRegistrationException):
        user_actions.validate_password(
            strategy,
            backend,
            pipeline_index=0,
            user=None,
            flow=SocialAuthState.FLOW_LOGIN,
        )


def test_user_not_active(rf, user):
    """Tests that an inactive user raises auth error, InvalidPasswordException"""
    user.set_password("abc123")
    user.is_active = False
    user.save()
    request = rf.post("/complete/email", {"password": "abc123", "email": user.email})
    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()
    strategy = load_strategy(request)
    backend = load_backend(strategy, "email", None)

    with pytest.raises(InvalidPasswordException):
        user_actions.validate_password(
            strategy,
            backend,
            pipeline_index=0,
            user=user,
            flow=SocialAuthState.FLOW_LOGIN,
        )


@pytest.mark.parametrize(
    "backend_name,flow",
    [
        ("notemail", None),
        ("notemail", SocialAuthState.FLOW_REGISTER),
        ("notemail", SocialAuthState.FLOW_LOGIN),
        (EmailAuth.name, None),
        (EmailAuth.name, SocialAuthState.FLOW_LOGIN),
    ],
)
def test_create_user_via_email_exit(mocker, backend_name, flow):
    """
    Tests that create_user_via_email returns if not using the email backend and attempting the
    'register' step of the auth flow
    """
    mock_strategy = mocker.Mock()
    mock_backend = mocker.Mock()
    mock_backend.name = backend_name
    assert (
        user_actions.create_user_via_email(
            mock_strategy, mock_backend, pipeline_index=0, flow=flow
        )
        == {}
    )

    mock_strategy.request_data.assert_not_called()


@responses.activate
@pytest.mark.django_db
def test_create_user_via_email(
    mocker, mock_email_backend, mock_create_user_strategy, settings
):
    """
    Tests that create_user_via_email creates a user via social_core.pipeline.user.create_user_via_email
    and sets a name and password
    """
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )
    email = "user@example.com"
    response = user_actions.create_user_via_email(
        mock_create_user_strategy,
        mock_email_backend,
        details=dict(email=email),
        pipeline_index=0,
        flow=SocialAuthState.FLOW_REGISTER,
    )
    assert isinstance(response["user"], User) is True
    assert response["user"].username == "custom-username"
    assert response["user"].is_active is True
    assert response["username"] == "custom-username"
    assert response["is_new"] is True


@pytest.mark.django_db
def test_create_user_via_email_no_data(mocker, mock_email_backend):
    """Tests that create_user_via_email raises an error if no data for name and password provided"""
    mock_strategy = mocker.Mock()
    mock_strategy.request_data.return_value = {}
    with pytest.raises(RequirePasswordAndPersonalInfoException):
        user_actions.create_user_via_email(
            mock_strategy,
            mock_email_backend,
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )


@pytest.mark.django_db
def test_create_user_via_email_with_shorter_name(mocker, mock_email_backend):
    """Tests that create_user_via_email raises an error if name field is shorter than 2 characters"""
    mock_strategy = mocker.Mock()
    mock_strategy.request_data.return_value = {
        "name": "a",
        "password": "password1",
        "username": "custom-username",
        "legal_address": {
            "first_name": "Jane",
            "last_name": "Doe",
            "country": "US",
        },
    }

    with pytest.raises(RequirePasswordAndPersonalInfoException) as exc:
        user_actions.create_user_via_email(
            mock_strategy,
            mock_email_backend,
            details=dict(email="test@example.com"),
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )

    assert exc.value.errors == ["Full name must be at least 2 characters long."]


@pytest.mark.django_db
def test_create_user_via_email_existing_user_raises(
    user, mock_email_backend, mock_create_user_strategy
):
    """Tests that create_user_via_email raises an error if a user already exists in the pipeline"""
    with pytest.raises(UnexpectedExistingUserException):
        user_actions.create_user_via_email(
            mock_create_user_strategy,
            mock_email_backend,
            user=user,
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )


def test_create_user_via_email_create_fail(
    mocker, mock_email_backend, mock_create_user_strategy
):
    """Tests that create_user_via_email raises an error if user creation fails"""
    mock_serializer_obj = mocker.Mock()
    mock_serializer_obj.is_valid = mocker.Mock(return_value=True)
    mock_serializer_obj.save = mocker.Mock(side_effect=ValueError)
    patched_user_serializer = mocker.patch(
        "authentication.pipeline.user.UserSerializer", return_value=mock_serializer_obj
    )
    with pytest.raises(UserCreationFailedException):
        user_actions.create_user_via_email(
            mock_create_user_strategy,
            mock_email_backend,
            details=dict(email="someuser@example.com"),
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )
    patched_user_serializer.assert_called_once()


def test_create_user_via_email_validation(
    mocker, mock_email_backend, mock_create_user_strategy
):
    """Tests that create_user_via_email raises an exception if serializer validation fails"""
    mock_serializer_obj = mocker.Mock()
    mock_serializer_obj.is_valid = mocker.Mock(return_value=False)
    mock_serializer_obj.errors = {
        "non_field_errors": ["non field error"],
        "username": "Invalid username",
    }
    patched_user_serializer = mocker.patch(
        "authentication.pipeline.user.UserSerializer", return_value=mock_serializer_obj
    )
    with pytest.raises(RequirePasswordAndPersonalInfoException) as exc:
        user_actions.create_user_via_email(
            mock_create_user_strategy,
            mock_email_backend,
            details=dict(email="someuser@example.com"),
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )
    patched_user_serializer.assert_called_once()
    assert exc.value.errors == mock_serializer_obj.errors["non_field_errors"]
    assert exc.value.field_errors == {"username": "Invalid username"}


@pytest.mark.django_db
def test_create_user_via_email_unique(
    mocker, mock_email_backend, mock_create_user_strategy
):
    """Tests that create_user_via_email raises an exception the given username is not unique"""
    email = "user@example.com"
    username = mock_create_user_strategy.request_data.return_value["username"]
    mock_serializer_obj = mocker.Mock()
    mock_serializer_obj.is_valid = mocker.Mock(return_value=True)
    mock_serializer_obj.save = mocker.Mock(side_effect=IntegrityError)
    patched_user_serializer = mocker.patch(
        "authentication.pipeline.user.UserSerializer", return_value=mock_serializer_obj
    )
    with pytest.raises(RequirePasswordAndPersonalInfoException) as exc:
        user_actions.create_user_via_email(
            mock_create_user_strategy,
            mock_email_backend,
            details=dict(email=email),
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )
    patched_user_serializer.assert_called_once()
    assert exc.value.field_errors == {
        "username": f"The username '{username}' is already taken. Please try a different username."
    }


@pytest.mark.parametrize("hijacked", [True, False])
def test_forbid_hijack(mocker, hijacked):
    """
    Tests that forbid_hijack action raises an exception if a user is hijacked
    """
    mock_strategy = mocker.Mock()
    mock_strategy.session_get.return_value = hijacked

    mock_backend = mocker.Mock(name="email")

    args = [mock_strategy, mock_backend]
    kwargs = {"flow": SocialAuthState.FLOW_LOGIN}

    if hijacked:
        with pytest.raises(ValueError):
            user_actions.forbid_hijack(*args, **kwargs)
    else:
        assert user_actions.forbid_hijack(*args, **kwargs) == {}


@pytest.mark.parametrize("raises_error", [True, False])
@pytest.mark.parametrize(
    "is_active, is_new, creates_records",
    [
        [True, True, True],
        [True, False, False],
        [False, True, False],
        [False, False, False],
    ],
)
def test_create_openedx_user(
    mocker, user, raises_error, is_active, is_new, creates_records
):  # pylint: disable=too-many-arguments
    """Test that activate_user takes the correct action"""
    user.is_active = is_active

    mock_create_user_api = mocker.patch(
        "authentication.pipeline.user.openedx_api.create_user"
    )
    if raises_error:
        mock_create_user_api.side_effect = Exception("error")
    mock_create_user_task = mocker.patch(
        "authentication.pipeline.user.openedx_tasks.create_user_from_id"
    )

    assert user_actions.create_openedx_user(None, None, user=user, is_new=is_new) == {}

    if creates_records:
        mock_create_user_api.assert_called_once_with(user)

        if raises_error:
            mock_create_user_task.apply_async.assert_called_once_with(
                (user.id,), countdown=60
            )
        else:
            mock_create_user_task.apply_async.assert_not_called()
    else:
        mock_create_user_api.assert_not_called()
        mock_create_user_task.apply_async.assert_not_called()


@pytest.mark.parametrize(
    "backend_name,flow,data",
    [
        ("notemail", SocialAuthState.FLOW_REGISTER, {}),
        ("notemail", SocialAuthState.FLOW_LOGIN, dict(email="test@example.com")),
    ],
)
def test_validate_email_backend(mocker, backend_name, flow, data):
    """Tests validate_email with data and flows"""
    mock_strategy = mocker.Mock()
    mock_backend = mocker.Mock()
    mock_backend.name = backend_name
    mock_strategy.request_data.return_value = data
    assert (
        user_actions.validate_email(
            mock_strategy, mock_backend, pipeline_index=0, flow=flow
        )
        == {}
    )

    mock_strategy.request_data.assert_called_once()


@pytest.mark.django_db
def test_create_user_when_email_blocked(mocker):
    """Tests that validate_email raises an error if user email is blocked"""
    mock_strategy = mocker.Mock()
    mock_email_backend = mocker.Mock()
    mock_strategy.request_data.return_value = {
        "email": "test@example.com",
        "flow": "register",
    }
    mocker.patch(
        "authentication.pipeline.user.is_user_email_blocked", return_value=True
    )
    with pytest.raises(EmailBlockedException):
        user_actions.validate_email(
            mock_strategy,
            mock_email_backend,
            pipeline_index=0,
            flow=SocialAuthState.FLOW_REGISTER,
        )
