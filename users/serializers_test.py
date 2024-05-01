"""Tests for users.serializers"""

import pytest
import responses
from django.contrib.auth.models import AnonymousUser
from django.test.client import RequestFactory
from pytest_lazyfixture import lazy_fixture
from requests import HTTPError
from requests.exceptions import ConnectionError as RequestsConnectionError
from rest_framework import status
from rest_framework.exceptions import ValidationError

from fixtures.common import (
    valid_address_dict,
)
from openedx.api import OPENEDX_REGISTRATION_VALIDATION_PATH
from openedx.exceptions import EdxApiRegistrationValidationException
from users.factories import UserFactory
from users.models import HIGHEST_EDUCATION_CHOICES, ChangeEmailRequest, LegalAddress
from users.serializers import (
    ChangeEmailRequestUpdateSerializer,
    LegalAddressSerializer,
    UserSerializer,
)

# pylint:disable=redefined-outer-name

USERNAME = "my-username"


@pytest.fixture
def application(settings):  # noqa: PT004
    """Test data and settings needed for create_edx_user tests"""
    settings.OPENEDX_API_BASE_URL = "http://example.com"


def test_validate_legal_address(valid_address_dict):
    """Test that correct address data validates"""
    serializer = LegalAddressSerializer(data=valid_address_dict)
    assert serializer.is_valid() is True


@pytest.mark.parametrize(
    "field,value,error",  # noqa: PT006
    [
        ["first_name", "", "This field may not be blank."],  # noqa: PT007
        ["last_name", "", "This field may not be blank."],  # noqa: PT007
        ["country", "", "This field may not be blank."],  # noqa: PT007
        ["country", None, "This field may not be null."],  # noqa: PT007
    ],
)
def test_validate_required_fields(valid_address_dict, field, value, error):
    """Test that missing required fields causes a validation error"""
    valid_address_dict[field] = value
    serializer = LegalAddressSerializer(data=valid_address_dict)
    assert serializer.is_valid() is False
    assert str(serializer.errors[field][0]) == error


@pytest.mark.parametrize(
    "address_type,error",  # noqa: PT006
    [
        [lazy_fixture("valid_address_dict"), None],  # noqa: PT007
        [lazy_fixture("intl_address_dict"), None],  # noqa: PT007
        [lazy_fixture("invalid_address_dict"), "Invalid state specified"],  # noqa: PT007
        [lazy_fixture("address_no_state_dict"), None],  # noqa: PT007
    ],
)
def test_legal_address_validate_state_field(address_type, error):
    """Tests that the LegalAddressSerializer properly validates the state field"""
    serializer = LegalAddressSerializer(data=address_type)
    if error is None:
        assert serializer.is_valid()
    else:
        assert serializer.is_valid() is False
        assert error in serializer.errors["state"]


def test_update_user_serializer(settings, user, valid_address_dict):
    """Test that a UserSerializer can be updated properly"""
    serializer = UserSerializer(
        instance=user,
        data={"password": "AgJw0123", "legal_address": valid_address_dict},
        partial=True,
    )
    assert serializer.is_valid()
    serializer.save()
    assert isinstance(user.legal_address, LegalAddress)


@responses.activate
@pytest.mark.django_db
@pytest.mark.parametrize("test_case_dup", [True, False])
def test_create_user_serializer(settings, valid_address_dict, test_case_dup):
    """Test that a UserSerializer can be created properly"""
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )
    serializer = UserSerializer(
        data={
            "username": "fakename",
            "email": "fake@fake.edu",
            "password": "fake",
            "legal_address": valid_address_dict,
        }
    )

    assert serializer.is_valid()
    user = serializer.save()
    assert user.is_active is True

    if test_case_dup:
        serializer = UserSerializer(
            data={
                "username": "fakename",
                "email": "FAKE@FAKE.EDU",
                "password": "fake",
                "legal_address": valid_address_dict,
            }
        )

        assert not serializer.is_valid()


def test_update_email_change_request_existing_email(user):
    """Test that update change email request gives validation error for existing user email"""
    new_user = UserFactory.create()
    change_request = ChangeEmailRequest.objects.create(
        user=user, new_email=new_user.email
    )
    serializer = ChangeEmailRequestUpdateSerializer(change_request, {"confirmed": True})

    with pytest.raises(ValidationError):  # noqa: PT012
        serializer.is_valid()
        serializer.save()


def test_create_email_change_request_same_email(user):
    """Test that update change email request gives validation error for same user email"""
    change_request = ChangeEmailRequest.objects.create(user=user, new_email=user.email)
    serializer = ChangeEmailRequestUpdateSerializer(change_request, {"confirmed": True})

    with pytest.raises(ValidationError):  # noqa: PT012
        serializer.is_valid()
        serializer.save()


@pytest.mark.parametrize("raises_error", [False, True])
def test_update_user_email(mocker, user, raises_error):  # pylint: disable=too-many-arguments
    """Test that update edx user email takes the correct action"""

    mock_update_edx_user_email = mocker.patch("openedx.tasks.api.update_edx_user_email")

    new_user = UserFactory.create()
    if raises_error:
        mock_update_edx_user_email.side_effect = Exception("error")
        new_email = new_user.email
    else:
        new_email = "abc@example.com"
    mock_change_edx_user_email_task = mocker.patch(
        "openedx.tasks.change_edx_user_email_async"
    )

    change_request = ChangeEmailRequest.objects.create(user=user, new_email=new_email)
    serializer = ChangeEmailRequestUpdateSerializer(change_request, {"confirmed": True})
    try:
        serializer.is_valid()
        serializer.save()
    except ValidationError:
        pass

    if raises_error:
        mock_update_edx_user_email.assert_not_called()
    else:
        mock_update_edx_user_email.assert_called_once_with(user)
    mock_change_edx_user_email_task.apply_async.assert_not_called()


@responses.activate
@pytest.mark.django_db
@pytest.mark.parametrize(
    "new_username, expect_valid, expect_saved_username",  # noqa: PT006
    [
        [f"{USERNAME}-1", True, f"{USERNAME}-1"],  # noqa: PT007
        [" My-Üsérname 1 ", True, "My-Üsérname 1"],  # noqa: PT007
        ["my@username", False, None],  # noqa: PT007
        ["my>username>1", False, None],  # noqa: PT007
        [f"   {USERNAME.upper()}  ", False, None],  # noqa: PT007
    ],
)
def test_username_validation(
    valid_address_dict, new_username, expect_valid, expect_saved_username, settings
):
    """
    UserSerializer should raise a validation error if the given username has invalid characters,
    or if there is already a user with that username after trimming and ignoring case. The saved
    username should have whitespace trimmed.
    """
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )
    # Seed an initial user with a constant username
    UserFactory.create(username=USERNAME)
    serializer = UserSerializer(
        data={
            "username": new_username,
            "email": "email@example.com",
            "password": "abcdefghi123",
            "legal_address": valid_address_dict,
        }
    )
    is_valid = serializer.is_valid()
    assert is_valid is expect_valid
    if expect_valid:
        instance = serializer.save()
        assert instance.username == expect_saved_username


@responses.activate
def test_username_validation_exception(user, settings):
    """
    UserSerializer should raise a EdxApiRegistrationValidationException if the username already exists
    in OpenEdx.
    """
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={
            "validation_decisions": {
                "username": f"It looks like {user.username} belongs to an existing account. Try again with a different username."
            }
        },
        status=status.HTTP_200_OK,
    )
    # Seed an initial user with a constant username
    UserFactory.create(username=USERNAME)
    serializer = UserSerializer(
        data={
            "username": user.username,
            "email": "email@example.com",
            "password": "abcdefghi123",
            "legal_address": valid_address_dict,
        }
    )
    assert serializer.is_valid() is False
    assert (
        str(serializer.errors["username"][0])
        == "A user already exists with this username. Please try a different one."
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "exception_raised",
    [EdxApiRegistrationValidationException, RequestsConnectionError, HTTPError],
)
def test_username_validation_connection_exception(
    mocker, exception_raised, valid_address_dict
):
    """
    UserSerializer should raise a RequestsConnectionError or HTTPError if the connection to OpenEdx
    fails.  The serializer should raise a validation error.
    """
    mocker.patch("openedx.api.validate_username_with_edx", side_effect=exception_raised)

    serializer = UserSerializer(
        data={
            "username": "unique-username",
            "email": "email11111@example.com",
            "password": "abcdefghi123",
            "legal_address": valid_address_dict,
        }
    )
    with pytest.raises(Exception):  # noqa: B017, PT011
        assert serializer.is_valid() is False


@responses.activate
@pytest.mark.django_db
def test_user_create_required_fields_post(valid_address_dict, settings):
    """
    UserSerializer should raise a validation error if a new User is being created and certain fields aren't
    included in the data.
    """
    base_data = {
        "email": "email@example.com",
        "legal_address": valid_address_dict,
    }
    rf = RequestFactory()
    # Request path does not matter here
    request = rf.post("/")
    request.user = AnonymousUser()
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_REGISTRATION_VALIDATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )
    serializer = UserSerializer(
        data={**base_data, "username": USERNAME}, context={"request": request}
    )
    assert serializer.is_valid() is False
    assert "password" in serializer.errors
    assert str(serializer.errors["password"][0]) == "This field is required."
    serializer = UserSerializer(
        data={**base_data, "password": "abcdefghij1"}, context={"request": request}
    )
    assert serializer.is_valid() is False
    assert "username" in serializer.errors
    assert str(serializer.errors["username"][0]) == "This field is required."


@pytest.mark.django_db
def test_user_create_required_fields_not_post(valid_address_dict):
    """
    If UserSerializer is given no request in the context, or that request is not a POST,
    it should not raise a validation error if certain fields are not included.
    """
    base_data = {
        "email": "email@example.com",
        "legal_address": valid_address_dict,
    }
    serializer = UserSerializer(data=base_data)
    assert serializer.is_valid() is True
    rf = RequestFactory()
    # Request path does not matter here
    request = rf.patch("/")
    request.user = AnonymousUser()
    serializer = UserSerializer(data=base_data, context={"request": request})
    assert serializer.is_valid() is True


def test_legal_address_serializer_invalid_name(valid_address_dict):
    """Test that LegalAddressSerializer raises an exception if any if the first or last name is not valid"""

    # To make sure that this test isn't flaky, Checking all the character and sequences that should match our name regex

    # Case 1: Make sure that invalid character(s) doesn't exist within the name
    for invalid_character in "~!@&)(+:'.?/,`-":
        # Replace the invalid character on 3 different places within name for rigorous testing of this case
        valid_address_dict["first_name"] = (
            f"{invalid_character}First{invalid_character} Name{invalid_character}"
        )
        valid_address_dict["last_name"] = (
            f"{invalid_character}Last{invalid_character} Name{invalid_character}"
        )
        serializer = LegalAddressSerializer(data=valid_address_dict)
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    # Case 2: Make sure that name doesn't start with valid special character(s)
    # These characters are valid for a name but they shouldn't be at the start
    for valid_character in '^/$#*=[]`%_;<>{}"|':
        valid_address_dict["first_name"] = f"{valid_character}First"
        valid_address_dict["last_name"] = f"{valid_character}Last"
        serializer = LegalAddressSerializer(data=valid_address_dict)
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)


@pytest.mark.parametrize("invalid_profile", [True, False])
def test_update_user_serializer_with_profile(
    settings, user, valid_address_dict, user_profile_dict, invalid_profile
):
    """Tests that the UserSerializers works right with a supplied UserProfile"""

    if invalid_profile:
        user_profile_dict["year_of_birth"] = None

    serializer = UserSerializer(
        instance=user,
        data={
            "password": "AgJw0123",
            "legal_address": valid_address_dict,
            "user_profile": user_profile_dict,
        },
        partial=True,
    )

    if invalid_profile:
        assert not serializer.is_valid()
    else:
        assert serializer.is_valid()
        serializer.save()
        assert isinstance(user.legal_address, LegalAddress)


@pytest.mark.parametrize("test_incomplete_addl_fields", [0, 1, 2])
def test_update_user_serializer_sets_addl_field_flag(
    settings, user, valid_address_dict, user_profile_dict, test_incomplete_addl_fields
):
    """Tests that the UserSerializers works right with a supplied UserProfile"""

    if test_incomplete_addl_fields >= 1:
        user_profile_dict["highest_education"] = HIGHEST_EDUCATION_CHOICES[1][0]

    if test_incomplete_addl_fields == 2:
        user_profile_dict["type_is_student"] = True

    serializer = UserSerializer(
        instance=user,
        data={
            "password": "AgJw0123",
            "legal_address": valid_address_dict,
            "user_profile": user_profile_dict,
        },
        partial=True,
    )

    assert serializer.is_valid()
    serializer.save()

    user.refresh_from_db()

    if test_incomplete_addl_fields > 1:
        assert user.user_profile.addl_field_flag == True  # noqa: E712
    else:
        assert user.user_profile.addl_field_flag == False  # noqa: E712
