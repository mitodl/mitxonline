"""Auth pipline functions for user authentication"""
import json
import logging

import requests
from django.conf import settings
from django.db import IntegrityError
from django.db import transaction
from mitol.common.utils import dict_without_keys
from social_core.backends.email import EmailAuth
from authentication.backends.odl_open_id_connect import OdlOpenIdConnectAuth
from social_core.exceptions import AuthException
from social_core.pipeline.partial import partial

from authentication.api import create_user_with_generated_username
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
from users.models import LegalAddress, User, UserProfile
from authentication.utils import SocialAuthState, is_user_email_blocked
from openedx import api as openedx_api
from openedx import tasks as openedx_tasks
from users.serializers import UserSerializer
from users.utils import usernameify

log = logging.getLogger()

CREATE_OPENEDX_USER_RETRY_DELAY = 60
NAME_MIN_LENGTH = 2

# pylint: disable=keyword-arg-before-vararg


def validate_email_auth_request(
    strategy, backend, user=None, *args, **kwargs
):  # pylint: disable=unused-argument
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


def get_username(
    strategy, backend, user=None, *args, **kwargs
):  # pylint: disable=unused-argument
    """
    Gets the username for a user

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
    """
    return {"username": None if not user else strategy.storage.user.get_username(user)}


@partial
def create_user_via_oidc(
    strategy,
    backend,
    user=None,
    response=None,
    flow=None,
    current_partial=None,
    *args,
    **kwargs,
):  # pylint: disable=too-many-arguments,unused-argument
    """
    Creates a new user if one does not already exist, updates an existing user's attributes.
    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
        details (dict): Dict of user details
        flow (str): the type of flow (login or register)
        current_partial (Partial): the partial for the step in the pipeline
    """

    if backend.name == OdlOpenIdConnectAuth.name:
        data = response.copy()
        try:
            data["is_staff"] = (
                "is_staff" in data["resource_access"]["mitxonline-client-id"]["roles"]
            )
            data["is_superuser"] = (
                "is_superuser"
                in data["resource_access"]["mitxonline-client-id"]["roles"]
            )
        except KeyError:
            pass
    else:
        return {}

    if user is None:
        with transaction.atomic():

            if "is_staff" in data and "is_superuser" in data:
                user = User.objects.create_superuser(
                    data["preferred_username"],
                    email=data["email"],
                    password=None,
                    naname=data["name"],
                )
            else:
                user = User.objects.create_user(
                    data["email"], email=data["email"], password=None, name=data["name"]
                )
    else:
        user.username = data["email"]
        user.email = data["email"]
        user.name = data["name"]

    # Update user's legal address record.
    user.legal_address.first_name = data.get(
        "given_name", user.legal_address.first_name
    )
    user.legal_address.last_name = data.get("family_name", user.legal_address.last_name)
    user.legal_address.country = data.get("country", user.legal_address.country)
    user.legal_address.state = data.get("state", user.legal_address.state)

    # Update user's profile record.
    user.user_profile.gender = data.get("gender", user.user_profile.gender)
    user.user_profile.year_of_birth = data.get(
        "year_of_birth", user.user_profile.year_of_birth
    )
    user.user_profile.company = data.get("company", user.user_profile.company)
    user.user_profile.years_experience = data.get(
        "years_experience", user.user_profile.years_experience
    )
    user.user_profile.leadership_level = data.get(
        "leadership_level", user.user_profile.leadership_level
    )
    user.user_profile.highest_education = data.get(
        "highest_education", user.user_profile.highest_education
    )
    user.user_profile.type_is_student = data.get(
        "type_is_student", user.user_profile.type_is_student
    )
    user.user_profile.type_is_professional = data.get(
        "type_is_professional", user.user_profile.type_is_professional
    )
    user.user_profile.type_is_educator = data.get(
        "type_is_educator", user.user_profile.type_is_educator
    )
    user.user_profile.type_is_other = data.get(
        "type_is_other", user.user_profile.type_is_other
    )

    user.save()

    return {"is_new": True, "user": user, "username": user.username}


@partial
def create_user_via_email(
    strategy,
    backend,
    user=None,
    response=None,
    flow=None,
    current_partial=None,
    *args,
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
    serializer = UserSerializer(data=data, context=context)

    if not serializer.is_valid():
        e = RequirePasswordAndPersonalInfoException(
            backend,
            current_partial,
            errors=serializer.errors.get("non_field_errors"),
            field_errors=dict_without_keys(serializer.errors, "non_field_errors"),
        )

        raise e

        raise e

    try:
        created_user = serializer.save()
    except IntegrityError:
        # 'email' and 'username' are the only unique fields that can be supplied by the user at this point, and a user
        # cannot reach this point of the auth flow without a unique email, so we know that the IntegrityError is caused
        # by the username not being unique.
        username = data["username"]
        raise RequirePasswordAndPersonalInfoException(
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
    strategy, backend, user=None, flow=None, current_partial=None, *args, **kwargs
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
    if authentication_flow == SocialAuthState.FLOW_REGISTER and "email" in data:
        if is_user_email_blocked(data["email"]):
            raise EmailBlockedException(backend, current_partial)
    return {}


@partial
def validate_password(
    strategy, backend, user=None, flow=None, current_partial=None, *args, **kwargs
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
        RequirePasswordException: if the user password is invalid
    """
    if backend.name != EmailAuth.name or flow != SocialAuthState.FLOW_LOGIN:
        return {}

    data = strategy.request_data()
    if user is None:
        raise RequireRegistrationException(backend, current_partial)

    if "password" not in data:
        raise RequirePasswordException(backend, current_partial)

    password = data["password"]

    if not user or not user.check_password(password):
        raise InvalidPasswordException(backend, current_partial)

    return {}


def forbid_hijack(strategy, backend, **kwargs):  # pylint: disable=unused-argument
    """
    Forbid an admin user from trying to login/register while hijacking another user

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
    """
    # As first step in pipeline, stop a hijacking admin from going any further
    if strategy.session_get("is_hijacked_user"):
        raise AuthException("You are hijacking another user, don't try to login again")
    return {}


def activate_user(
    strategy, backend, user=None, is_new=False, **kwargs
):  # pylint: disable=unused-argument
    """
    Activate the user's account if they passed export controls

    Args:
        strategy (social_django.strategy.DjangoStrategy): the strategy used to authenticate
        backend (social_core.backends.base.BaseAuth): the backend being used to authenticate
        user (User): the current user
    """
    if user.is_active:
        return {}

    # export_inquiry = compliance_api.get_latest_exports_inquiry(user)
    #
    # # if the user has an export inquiry that is considered successful, activate them
    # if not compliance_api.is_exports_verification_enabled() or (
    #     export_inquiry is not None and export_inquiry.is_success
    # ):
    #     user.is_active = True
    #     user.save()

    user.is_active = True
    user.save()

    return {}


def create_openedx_user(
    strategy, backend, user=None, is_new=False, **kwargs
):  # pylint: disable=unused-argument
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
