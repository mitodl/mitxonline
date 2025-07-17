from urllib.parse import parse_qs, quote, urlencode, urlparse

import pytest
from django.urls import reverse
from pytest_lazy_fixtures import lf
from rest_framework import status

from authentication.api_gateway.views import AccountActionStartView
from users.api import User
from users.factories import UserFactory
from users.models import MALE, UserProfile

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("authentication.api_gateway.pytest_urls"),
]


def test_post_user_profile_detail(mocker, valid_address_dict, client, user):
    """Test that user can save profile details"""
    client.force_login(user)
    data = {
        "name": "John Doe",
        "username": "johndoe",
        "legal_address": valid_address_dict,
        "user_profile": {},
    }
    mock_create_edx_user = mocker.patch("openedx.api.create_edx_user")
    mock_create_edx_auth_token = mocker.patch("openedx.api.create_edx_auth_token")
    resp = client.post(
        reverse("profile-details-api"), data, content_type="application/json"
    )

    assert resp.status_code == status.HTTP_200_OK
    # Checks that user's name in database is also updated
    assert User.objects.get(pk=user.pk).name == data["name"]
    assert mock_create_edx_user.called is True
    assert mock_create_edx_auth_token.called is True

    data = {
        "name": "John Doe",
        "user_profile": {},
    }
    resp = client.post(
        reverse("profile-details-api"), data, content_type="application/json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_post_user_extra_detail(client, user):
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


def test_custom_login_view_authenticated_user_with_onboarding(settings, client):
    """Test GatewayLoginView for an authenticated user with incomplete onboarding"""
    settings.MITXONLINE_NEW_USER_LOGIN_URL = "/create-profile"

    client.force_login(UserFactory.create())

    qs = {"next": "/dashboard"}
    response = client.get(f"{reverse('gateway-login')}?{urlencode(qs)}")

    assert response.status_code == 302
    assert response.url == "/create-profile?next=%2Fdashboard"


def test_custom_login_view_authenticated_user_with_completed_onboarding(client):
    """Test that user who has completed onboarding is redirected to next url"""

    client.force_login(UserFactory.create(user_profile__completed_onboarding=True))

    qs = {"next": "/dashboard"}
    response = client.get(f"{reverse('gateway-login')}?{urlencode(qs)}")

    assert response.status_code == 302
    assert response.url == "/dashboard"


@pytest.mark.parametrize(
    ("auth_user", "url", "expected_redirect_url"),
    [
        (
            lf("user"),
            "/logout?no_redirect=1",
            "http://mitxonline.odl.local/logout/oidc",
        ),
        (None, "/logout?no_redirect=1", "http://mitxonline.odl.local"),
        (
            lf("user"),
            "/logout",
            "https://openedx.odl.local/logout?redirect_url=http%3A%2F%2Fmitxonline.odl.local",
        ),
        (
            None,
            "/logout",
            "https://openedx.odl.local/logout?redirect_url=http%3A%2F%2Fmitxonline.odl.local",
        ),
    ],
)
def test_gateway_logout(client, auth_user, url, expected_redirect_url):
    """Test that the api gateway logout works"""
    if auth_user is not None:
        client.force_login(auth_user)

    resp = client.get(url)

    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.headers["Location"] == expected_redirect_url


def test_logout_complete(client):
    """Test that logout complete works"""
    resp = client.get("/logout/complete")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"message": "Logout complete"}


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(action, id=f"/account/action/start/{action[0]}")
        for action in AccountActionStartView.ACTION_MAPPING.items()
    ],
)
def test_account_action_start(settings, client, action):
    url_action, kc_action = action

    resp = client.get(
        f"{reverse('account-action-start', kwargs={'action': url_action})}?next={quote('/dashboard')}"
    )

    assert resp.status_code == status.HTTP_302_FOUND
    parsed = urlparse(resp.headers["Location"])

    assert parsed.scheme == "http"
    assert parsed.netloc == "keycloak"
    assert parsed.path == "/realms/ol-test/protocol/openid-connect/auth"

    assert parse_qs(parsed.query) == {
        "kc_action": [kc_action],
        "scope": ["openid"],
        "response_type": ["code"],
        "client_id": ["mitxonline"],
        "redirect_uri": [
            f"{settings.SITE_BASE_URL}/account/action/complete?{urlencode({'next': '/dashboard'})}"
        ],
    }


def test_account_action_callback(client):
    resp = client.get(f"{reverse('account-action-complete')}?{quote('/dashboard')}")
    assert resp.status_code == status.HTTP_302_FOUND
    assert resp.headers["Location"] == "/dashboard"
