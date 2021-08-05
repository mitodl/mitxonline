"""Tests for users.serializers"""
import pytest
from rest_framework.exceptions import ValidationError

from users.factories import UserFactory
from users.models import ChangeEmailRequest, LegalAddress
from users.serializers import (
    ChangeEmailRequestUpdateSerializer,
    LegalAddressSerializer,
    UserSerializer,
)

# pylint:disable=redefined-outer-name


@pytest.fixture()
def sample_address():
    """Return a legal address"""
    return {
        "first_name": "Test",
        "last_name": "User",
        "country": "US",
    }


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


@pytest.mark.django_db
def test_create_user_serializer(settings, sample_address):
    """Test that a UserSerializer can be created properly"""
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
