"""Tests for users.serializers"""
from openedx.api import OPENEDX_VALIDATION_REGISTRATION_PATH
import pytest
import responses
from django.contrib.auth.models import AnonymousUser

from django.test.client import RequestFactory
from rest_framework.exceptions import ValidationError
from rest_framework import status

from users.factories import UserFactory
from users.models import ChangeEmailRequest, LegalAddress
from users.serializers import (
    ChangeEmailRequestUpdateSerializer,
    LegalAddressSerializer,
    UserSerializer,
)

# pylint:disable=redefined-outer-name

USERNAME = "my-username"


@pytest.fixture()
def sample_address():
    """Return a legal address"""
    return {
        "first_name": "Test",
        "last_name": "User",
        "country": "US",
    }


@pytest.fixture()
def application(settings):
    """Test data and settings needed for create_edx_user tests"""
    settings.OPENEDX_OAUTH_APP_NAME = "test_app_name"
    settings.OPENEDX_API_BASE_URL = "http://example.com"
    settings.MITX_ONLINE_OAUTH_PROVIDER = "test_provider"
    settings.MITX_ONLINE_REGISTRATION_ACCESS_TOKEN = "access_token"
    return Application.objects.create(
        name=settings.OPENEDX_OAUTH_APP_NAME,
        user=None,
        client_type="confidential",
        authorization_grant_type="authorization-code",
        skip_authorization=True,
    )


def test_validate_legal_address(sample_address):
    """Test that correct address data validates"""
    serializer = LegalAddressSerializer(data=sample_address)
    assert serializer.is_valid() is True


@pytest.mark.parametrize(
    "field,value,error",
    [
        ["first_name", "", "This field may not be blank."],
        ["last_name", "", "This field may not be blank."],
        ["country", "", "This field may not be blank."],
        ["country", None, "This field may not be null."],
    ],
)
def test_validate_required_fields(sample_address, field, value, error):
    """Test that missing required fields causes a validation error"""
    sample_address[field] = value
    serializer = LegalAddressSerializer(data=sample_address)
    assert serializer.is_valid() is False
    assert str(serializer.errors[field][0]) == error


def test_update_user_serializer(settings, user, sample_address):
    """Test that a UserSerializer can be updated properly"""
    serializer = UserSerializer(
        instance=user,
        data={"password": "AgJw0123", "legal_address": sample_address},
        partial=True,
    )
    assert serializer.is_valid()
    serializer.save()
    assert isinstance(user.legal_address, LegalAddress)


@responses.activate
@pytest.mark.django_db
def test_create_user_serializer(settings, sample_address):
    """Test that a UserSerializer can be created properly"""
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_VALIDATION_REGISTRATION_PATH,
        json={"validation_decisions": {"username": ""}},
        status=status.HTTP_200_OK,
    )
    serializer = UserSerializer(
        data={
            "username": "fakename",
            "email": "fake@fake.edu",
            "password": "fake",
            "legal_address": sample_address,
        }
    )

    assert serializer.is_valid()
    user = serializer.save()


def test_update_email_change_request_existing_email(user):
    """Test that update change email request gives validation error for existing user email"""
    new_user = UserFactory.create()
    change_request = ChangeEmailRequest.objects.create(
        user=user, new_email=new_user.email
    )
    serializer = ChangeEmailRequestUpdateSerializer(change_request, {"confirmed": True})

    with pytest.raises(ValidationError):
        serializer.is_valid()
        serializer.save()


def test_create_email_change_request_same_email(user):
    """Test that update change email request gives validation error for same user email"""
    change_request = ChangeEmailRequest.objects.create(user=user, new_email=user.email)
    serializer = ChangeEmailRequestUpdateSerializer(change_request, {"confirmed": True})

    with pytest.raises(ValidationError):
        serializer.is_valid()
        serializer.save()


@pytest.mark.parametrize("raises_error", [False, True])
def test_update_user_email(
    mocker, user, raises_error
):  # pylint: disable=too-many-arguments
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
    "new_username, expect_valid, expect_saved_username",
    [
        [f"{USERNAME}-1", True, f"{USERNAME}-1"],
        [" My-Üsérname 1 ", True, "My-Üsérname 1"],
        ["my@username", False, None],
        ["my>username>1", False, None],
        [f"   {USERNAME.upper()}  ", False, None],
    ],
)
def test_username_validation(
    sample_address, new_username, expect_valid, expect_saved_username, settings
):
    """
    UserSerializer should raise a validation error if the given username has invalid characters,
    or if there is already a user with that username after trimming and ignoring case. The saved
    username should have whitespace trimmed.
    """
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_VALIDATION_REGISTRATION_PATH,
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
            "legal_address": sample_address,
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
    UserSerializer should raise a validation error if the given username has invalid characters,
    or if there is already a user with that username after trimming and ignoring case. The saved
    username should have whitespace trimmed.
    """
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_VALIDATION_REGISTRATION_PATH,
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
            "legal_address": sample_address,
        }
    )
    assert serializer.is_valid() is False
    assert (
        str(serializer.errors["username"][0])
        == "A user already exists with this username. Please try a different one."
    )


@responses.activate
@pytest.mark.django_db
def test_user_create_required_fields_post(sample_address, settings):
    """
    UserSerializer should raise a validation error if a new User is being created and certain fields aren't
    included in the data.
    """
    base_data = {
        "email": "email@example.com",
        "legal_address": sample_address,
    }
    rf = RequestFactory()
    # Request path does not matter here
    request = rf.post("/")
    request.user = AnonymousUser()
    responses.add(
        responses.POST,
        settings.OPENEDX_API_BASE_URL + OPENEDX_VALIDATION_REGISTRATION_PATH,
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


def test_user_create_required_fields_not_post(sample_address):
    """
    If UserSerializer is given no request in the context, or that request is not a POST,
    it should not raise a validation error if certain fields are not included.
    """
    base_data = {
        "email": "email@example.com",
        "legal_address": sample_address,
    }
    serializer = UserSerializer(data=base_data)
    assert serializer.is_valid() is True
    rf = RequestFactory()
    # Request path does not matter here
    request = rf.patch("/")
    request.user = AnonymousUser()
    serializer = UserSerializer(data=base_data, context={"request": request})
    assert serializer.is_valid() is True


def test_legal_address_serializer_invalid_name(sample_address):
    """Test that LegalAddressSerializer raises an exception if any if the first or last name is not valid"""

    # To make sure that this test isn't flaky, Checking all the character and sequences that should match our name regex

    # Case 1: Make sure that invalid character(s) doesn't exist within the name
    for invalid_character in "~!@&)(+:'.?/,`-":
        # Replace the invalid character on 3 different places within name for rigorous testing of this case
        sample_address["first_name"] = "{0}First{0} Name{0}".format(invalid_character)
        sample_address["last_name"] = "{0}Last{0} Name{0}".format(invalid_character)
        serializer = LegalAddressSerializer(data=sample_address)
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    # Case 2: Make sure that name doesn't start with valid special character(s)
    # These characters are valid for a name but they shouldn't be at the start
    for valid_character in '^/$#*=[]`%_;<>{}"|':
        sample_address["first_name"] = "{}First".format(valid_character)
        sample_address["last_name"] = "{}Last".format(valid_character)
        serializer = LegalAddressSerializer(data=sample_address)
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
