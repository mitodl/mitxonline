"""Auth pipline functions for user authentication"""

import logging

from django.db import IntegrityError
from mitol.common.utils import dict_without_keys
from social_core.backends.email import EmailAuth
from social_core.exceptions import AuthException
from social_core.pipeline.partial import partial
from social_core.pipeline.user import create_user

from authentication.backends.ol_open_id_connect import OlOpenIdConnectAuth
from authentication.exceptions import (
    EmailBlockedException,
    InvalidPasswordException,
    RequireEmailException,
    RequirePasswordAndPersonalInfoException,
    RequirePasswordException,
    RequireRegistrationException,
    UnexpectedExistingUserException,
    UserCreationFailedException,
)
from authentication.utils import SocialAuthState, is_user_email_blocked
from openedx import api as openedx_api
from openedx import tasks as openedx_tasks
from users.serializers import UserSerializer

log = logging.getLogger()

CREATE_OPENEDX_USER_RETRY_DELAY = 60
NAME_MIN_LENGTH = 2

# pylint: disable=keyword-arg-before-vararg


def forbid_hijack(strategy, backend, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG001
    """
    Forbid an admin user from trying to login/register while hijacking another user

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
    """
    # As first step in pipeline, stop a hijacking admin from going any further
    if bool(strategy.session_get("hijack_history")):
        raise AuthException("You are hijacking another user, don't try to login again")  # noqa: EM101
    return {}


# Pipeline steps for OIDC logins


def create_ol_oidc_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    Create the user if we're using the ol-oidc backend.

    This also does a blocked user check and makes sure there's an email address.
    If the created user is new, we make sure they're set active. (If the user is
    inactive, they'll get knocked out of the pipeline elsewhere.)
    """

    if backend.name != OlOpenIdConnectAuth.name:
        return {}

    if "email" not in details:
        raise RequireEmailException(backend, None)

    if "email" in details and is_user_email_blocked(details["email"]):
        raise EmailBlockedException(backend, None)

    retval = create_user(strategy, details, backend, user, *args, **kwargs)

    # When we have deprecated direct login, remove this and default the is_active
    # flag to True in the User model.
    if retval.get("is_new"):
        retval["user"].is_active = True
        retval["user"].save()

    return retval


# Pipeline steps for email logins


def validate_email_auth_request(strategy, backend, user=None, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG001
    """
    Validates an auth request for email

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
    """
    if backend.name != EmailAuth.name:
        return {}

    # if there's a user, force this to be a login
    if user is not None:
        return {"flow": SocialAuthState.FLOW_LOGIN}

    return {}


def get_username(strategy, backend, user=None, details=None, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG001
    """
    Gets the username for a user

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
    """

    if backend and backend.name == OlOpenIdConnectAuth.name:
        return {"username": details["username"] if not user else user.username}

    return {"username": None if not user else strategy.storage.user.get_username(user)}


@partial
def create_user_via_email(
    strategy,
    backend,
    user=None,
    flow=None,
    current_partial=None,
    *args,  # noqa: ARG001
    **kwargs,
):  # pylint: disable=too-many-arguments,unused-argument
    """
    Creates a new user if needed and sets the password and name.
    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
        details (dict): Dict of user details
        flow (str): the type of flow (login or register)
        current_partial (Partial): the partial for the step in the pipeline

    Raises:
        RequirePasswordAndPersonalInfoException: if the user hasn't set password or name
    """
    if backend.name != EmailAuth.name or flow != SocialAuthState.FLOW_REGISTER:
        return {}

    if user is not None:
        raise UnexpectedExistingUserException(backend, current_partial)

    context = {}
    data = strategy.request_data().copy()
    expected_data_fields = {"name", "password", "username"}
    if any(field for field in expected_data_fields if field not in data):
        raise RequirePasswordAndPersonalInfoException(backend, current_partial)
    if len(data.get("name", 0)) < NAME_MIN_LENGTH:
        raise RequirePasswordAndPersonalInfoException(
            backend,
            current_partial,
            errors=["Full name must be at least 2 characters long."],
        )

    data["email"] = kwargs.get("email", kwargs.get("details", {}).get("email"))
    data["is_active"] = True
    serializer = UserSerializer(data=data, context=context)

    if not serializer.is_valid():
        e = RequirePasswordAndPersonalInfoException(
            backend,
            current_partial,
            errors=serializer.errors.get("non_field_errors"),
            field_errors=dict_without_keys(serializer.errors, "non_field_errors"),
        )

        raise e

    try:
        created_user = serializer.save()
    except IntegrityError:
        # 'email' and 'username' are the only unique fields that can be supplied by the user at this point, and a user
        # cannot reach this point of the auth flow without a unique email, so we know that the IntegrityError is caused
        # by the username not being unique.
        username = data["username"]
        raise RequirePasswordAndPersonalInfoException(  # noqa: B904
            backend,
            current_partial,
            field_errors={
                "username": f"The username '{username}' is already taken. Please try a different username."
            },
        )
    except Exception as exc:
        raise UserCreationFailedException(backend, current_partial) from exc

    return {"is_new": True, "user": created_user, "username": created_user.username}


@partial
def validate_email(
    strategy,
    backend,
    user=None,  # noqa: ARG001
    flow=None,  # noqa: ARG001
    current_partial=None,
    *args,  # noqa: ARG001
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Validates a user's email for register

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
        flow (str): the type of flow (login or register)
        current_partial (Partial): the partial for the step in the pipeline

    Raises:
        EmailBlockedException: if the user email is blocked
    """
    data = strategy.request_data()
    authentication_flow = data.get("flow")
    if authentication_flow == SocialAuthState.FLOW_REGISTER and "email" in data:  # noqa: SIM102
        if is_user_email_blocked(data["email"]):
            raise EmailBlockedException(backend, current_partial)
    return {}


@partial
def validate_password(
    strategy,
    backend,
    user=None,
    flow=None,
    current_partial=None,
    *args,  # noqa: ARG001
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Validates a user's password for login

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
        flow (str): the type of flow (login or register)
        current_partial (Partial): the partial for the step in the pipeline

    Raises:
        RequirePasswordException: if the user password is not provided
        InvalidPasswordException: if the password does not match the user, or the user is not active.
    """
    if backend.name != EmailAuth.name or flow != SocialAuthState.FLOW_LOGIN:
        return {}

    data = strategy.request_data()
    if user is None:
        raise RequireRegistrationException(backend, current_partial)

    if "password" not in data:
        raise RequirePasswordException(backend, current_partial)

    password = data["password"]

    if not user or not user.check_password(password) or not user.is_active:
        raise InvalidPasswordException(backend, current_partial)

    return {}


def create_openedx_user(strategy, backend, user=None, is_new=False, **kwargs):  # pylint: disable=unused-argument  # noqa: FBT002, ARG001
    """
    Create a user in the openedx, deferring a retry via celery if it fails

    Args:
        user (users.models.User): the user that was just created
        is_new (bool): True if the user was just created
    """
    if not is_new or not user.is_active:
        return {}

    try:
        openedx_api.create_user(user)
    except Exception:  # pylint: disable=broad-except
        log.exception("Error creating openedx user records on User create")
        # try again later
        openedx_tasks.create_user_from_id.apply_async(
            (user.id,), countdown=CREATE_OPENEDX_USER_RETRY_DELAY
        )

    return {}
