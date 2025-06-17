import pytest
from django.test import RequestFactory
from django.urls import reverse
from rest_framework import status

from authentication.api_gateway.views import GatewayLoginView
from openedx.models import OpenEdxUser
from users.api import User
from users.factories import UserFactory
from users.models import MALE, UserProfile


@pytest.mark.django_db
def test_post_user_profile_detail(mocker, valid_address_dict, client, user):
    """Test that user can save profile details"""
    client.force_login(user)
    mock_client = mocker.MagicMock()
    edx_api_mock = mocker.patch("openedx.api.get_edx_api_client", return_value=mock_client)
    data = {
        "name": "John Doe",
        "username": "johndoe",
        "legal_address": valid_address_dict,
        "user_profile": {},
    }
    resp = client.post(
        reverse("profile-details-api"), data, content_type="application/json"
    )

    assert resp.status_code == status.HTTP_200_OK
    # Checks that user's name in database is also updated
    assert User.objects.get(pk=user.pk).name == data["name"]
    assert OpenEdxUser.objects.get(user=user).has_been_synced is True

    assert edx_api_mock.called is True

    data = {
        "name": "John Doe",
        "user_profile": {},
    }
    resp = client.post(
        reverse("profile-details-api"), data, content_type="application/json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_post_user_extra_detail(mocker, client, user):
    """Test that user can save profile extra details"""
    client.force_login(user)
    data = {
        "gender": MALE,
        "birth_year": "1990",
        "company": "TechCorp",
        "job_title": "Engineer",
        "industry": "Technology",
        "job_function": "Development",
        "years_experience": "5",
        "company_size": 999,
        "leadership_level": "Mid-level",
        "highest_education": "Bachelor's degree",
    }
    resp = client.post(
        reverse("profile-extra-api"), data, content_type="application/json"
    )

    assert resp.status_code == status.HTTP_200_OK
    user_profile = UserProfile.objects.get(user=user)
    assert user_profile.company == "TechCorp"
    assert user_profile.job_title == "Engineer"

    data = {
        "gender": "",
        "birth_year": "not-a-year",
        "company": "",
    }
    resp = client.post(
        reverse("profile-extra-api"), data, content_type="application/json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_custom_login_view_authenticated_user_with_onboarding(mocker):
    """Test GatewayLoginView for an authenticated user with incomplete onboarding"""
    factory = RequestFactory()
    request = factory.get(reverse("login"), {"next": "/dashboard"})
    user = UserFactory()
    request.user = user
    mocker.patch(
        "authentication.social_auth.views.settings.MITXONLINE_NEW_USER_LOGIN_URL",
        "/create-profile",
    )

    response = GatewayLoginView().get(request)

    assert response.status_code == 302
    assert response.url == "/create-profile?next=%2Fdashboard"


@pytest.mark.django_db
def test_custom_login_view_authenticated_user_with_completed_onboarding(mocker):
    """Test that user who has completed onboarding is redirected to next url"""
    factory = RequestFactory()
    request = factory.get(reverse("login"), {"next": "/dashboard"})
    user = UserFactory(user_profile__completed_onboarding=True)
    request.user = user

    response = GatewayLoginView().get(request)

    assert response.status_code == 302
    assert response.url == "/dashboard"
