import pytest
import responses
from rest_framework import status

from authentication.api_gateway.serializers import (
    RegisterDetailsSerializer,
    RegisterExtraDetailsSerializer,
)
from openedx.models import OpenEdxUser
from users.factories import UserFactory


@pytest.mark.django_db
def test_register_details_serializer_create(
    mocker, user, valid_address_dict, user_profile_dict, rf
):
    """Test the create method of RegisterDetailsSerializer"""

    request = rf.post("/api/profile/details/")
    request.user = user

    data = {
        "name": "John Doe",
        "username": "johndoe",
        "legal_address": valid_address_dict,
        "user_profile": user_profile_dict,
    }
    mock_create_edx_user = mocker.patch("openedx.api.create_edx_user")
    mock_create_edx_auth_token = mocker.patch("openedx.api.create_edx_auth_token")

    serializer = RegisterDetailsSerializer(data=data, context={"request": request})
    assert serializer.is_valid(), serializer.errors

    assert serializer.is_valid()
    user = serializer.save()
    assert user.name == "John Doe"
    validated_data = serializer.validated_data
    assert validated_data["user_profile"]["gender"] is None
    assert validated_data["user_profile"]["year_of_birth"] == 1980
    assert validated_data["legal_address"]["country"] == "US"
    assert mock_create_edx_user.call_count == 1
    assert mock_create_edx_auth_token.call_count == 1


@pytest.mark.django_db
@responses.activate
def test_register_no_edx_user(  # noqa: PLR0913
    mocker, settings, user, valid_address_dict, user_profile_dict, rf
):
    """Test the create method of RegisterDetailsSerializer"""

    request = rf.post("/api/profile/details/")

    user = UserFactory.create(no_openedx_user=True, no_openedx_api_auth=True)
    request.user = user

    responses.add(
        responses.POST,
        f"{settings.OPENEDX_API_BASE_URL}/user_api/v1/account/registration/",
        json=dict(success=True),  # noqa: C408
        status=status.HTTP_200_OK,
    )

    patched_create_edx_auth_token = mocker.patch("openedx.api.create_edx_auth_token")

    data = {
        "name": "John Doe",
        "username": "johndoe",
        "legal_address": valid_address_dict,
        "user_profile": user_profile_dict,
    }
    assert user.openedx_user is None

    serializer = RegisterDetailsSerializer(data=data, context={"request": request})
    assert serializer.is_valid(), serializer.errors

    assert serializer.is_valid()
    user = serializer.save()

    assert OpenEdxUser.objects.filter(user=user, has_been_synced=True).exists() is True
    assert patched_create_edx_auth_token.call_count == 1
    assert user.name == "John Doe"
    assert user.openedx_users.exists() is True
    assert user.openedx_users.first().has_been_synced is True
    validated_data = serializer.validated_data
    assert validated_data["user_profile"]["gender"] is None
    assert validated_data["user_profile"]["year_of_birth"] == 1980
    assert validated_data["legal_address"]["country"] == "US"


@pytest.mark.django_db
def test_register_details_serializer_invalid_data(user, invalid_address_dict, rf):
    """Test RegisterDetailsSerializer with invalid data"""
    request = rf.post("/api/profile/details/")
    request.user = user

    data = {
        "name": "John Doe",
        "username": "johndoe",
        "legal_address": invalid_address_dict,
        "user_profile": {},
    }

    serializer = RegisterDetailsSerializer(data=data, context={"request": request})

    assert serializer.is_valid() is not True


@pytest.mark.django_db
def test_register_extra_details_serializer_valid_data(user):
    """Test RegisterExtraDetailsSerializer with valid data"""
    data = {
        "gender": "Male",
        "birth_year": "1990",
        "company": "TechCorp",
        "job_title": "Engineer",
        "industry": "Technology",
        "job_function": "Development",
        "years_experience": "5",
        "company_size": "100-500",
        "leadership_level": "Mid-level",
        "highest_education": "Bachelor's",
    }

    serializer = RegisterExtraDetailsSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    validated_data = serializer.validated_data
    assert validated_data["gender"] == "Male"
    assert validated_data["birth_year"] == "1990"
    assert validated_data["company"] == "TechCorp"

@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "12345",
        "123",
        "  12345  ",
        "999999",
        "12",
    ],
)
def test_register_details_serializer_allows_numeric_only_name(  # noqa: PLR0913
    mocker, name, user, valid_address_dict, user_profile_dict, rf
):
    """Test RegisterDetailsSerializer allows names containing only numbers (edX supports this)"""
    request = rf.post("/api/profile/details/")
    request.user = user

    data = {
        "name": name.strip(),
        "username": "testuser",
        "legal_address": valid_address_dict,
        "user_profile": user_profile_dict,
    }

    mocker.patch("openedx.api.create_edx_user")
    mocker.patch("openedx.api.create_edx_auth_token")

    serializer = RegisterDetailsSerializer(data=data, context={"request": request})
    assert serializer.is_valid(), f"Serializer should accept numeric name '{name}'. Errors: {serializer.errors}"
