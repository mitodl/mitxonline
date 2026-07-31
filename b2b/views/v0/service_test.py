"""Tests for the service-to-service B2B views.

TEMPORARY -- delete alongside b2b/views/v0/service.py when org-manager status
becomes visible in Keycloak (mitodl/hq#10594).
"""

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc
from oauth2_provider.models import AccessToken, Application, get_application_model
from rest_framework import status
from rest_framework.test import APIClient

from b2b.factories import OrganizationPageFactory
from b2b.models import UserOrganization
from b2b.views.v0.service import MANAGER_CHECK_SCOPE
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def generate_token():
    """Return a unique opaque token value."""

    return uuid.uuid4().hex


@pytest.fixture
def api_client():
    """Unauthenticated API client."""

    return APIClient()


@pytest.fixture
def url():
    """The org-manager-check endpoint URL."""

    return reverse("b2b:service-organization-manager-check")


@pytest.fixture
def service_application():
    """A confidential client-credentials Application, as a service would use."""

    return get_application_model().objects.create(
        name="ol-analytics-api",
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
    )


def _token(application, scope):
    """Mint an access token for the application with the given scope."""

    return AccessToken.objects.create(
        user=None,
        application=application,
        token=generate_token(),
        scope=scope,
        expires=now_in_utc() + timedelta(hours=1),
    )


@pytest.fixture
def scoped_token(service_application):
    """A token carrying the manager-check scope."""

    return _token(service_application, MANAGER_CHECK_SCOPE)


@pytest.fixture
def org():
    """An organization with a known sso_organization_id."""

    return OrganizationPageFactory.create(sso_organization_id=uuid.uuid4())


def _auth(client, token):
    """Attach a bearer token to the client."""

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.token}")
    return client


def test_manager_returns_true(api_client, url, scoped_token, org):
    """A user with is_manager=True on the org is reported as a manager."""

    user = UserFactory.create()
    UserOrganization.objects.create(user=user, organization=org, is_manager=True)

    response = _auth(api_client, scoped_token).get(
        url,
        {
            "sso_organization_id": str(org.sso_organization_id),
            "user_global_id": user.global_id,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_manager": True}


def test_member_but_not_manager_returns_false(api_client, url, scoped_token, org):
    """Plain membership is not enough -- is_manager must be set.

    This is the whole reason the endpoint exists: the Keycloak token carries
    membership but not the manager flag.
    """

    user = UserFactory.create()
    UserOrganization.objects.create(user=user, organization=org, is_manager=False)

    response = _auth(api_client, scoped_token).get(
        url,
        {
            "sso_organization_id": str(org.sso_organization_id),
            "user_global_id": user.global_id,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_manager": False}


def test_manager_of_a_different_org_returns_false(api_client, url, scoped_token, org):
    """Managing one org must not confer manager status on another."""

    other_org = OrganizationPageFactory.create(sso_organization_id=uuid.uuid4())
    user = UserFactory.create()
    UserOrganization.objects.create(user=user, organization=other_org, is_manager=True)

    response = _auth(api_client, scoped_token).get(
        url,
        {
            "sso_organization_id": str(org.sso_organization_id),
            "user_global_id": user.global_id,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_manager": False}


@pytest.mark.parametrize(
    "unknown",
    [("user",), ("org",), ("user", "org")],
    ids=["unknown-user", "unknown-org", "both-unknown"],
)
def test_unknown_subject_fails_closed(api_client, url, scoped_token, org, unknown):
    """An unknown user or org answers false rather than 404.

    Fails closed, and avoids letting a caller enumerate which org UUIDs and
    user IDs exist here.
    """

    user = UserFactory.create()
    UserOrganization.objects.create(user=user, organization=org, is_manager=True)

    response = _auth(api_client, scoped_token).get(
        url,
        {
            "sso_organization_id": (
                str(uuid.uuid4()) if "org" in unknown else str(org.sso_organization_id)
            ),
            "user_global_id": (
                "no-such-global-id" if "user" in unknown else user.global_id
            ),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"is_manager": False}


def test_requires_authentication(api_client, url, org):
    """An unauthenticated call is rejected."""

    response = api_client.get(
        url,
        {
            "sso_organization_id": str(org.sso_organization_id),
            "user_global_id": "anything",
        },
    )

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_requires_the_manager_check_scope(api_client, url, service_application, org):
    """A valid token without the scope is rejected.

    The scope is the only thing standing between a service credential and the
    ability to ask about any user, so this is the load-bearing check.
    """

    wrong_scope_token = _token(service_application, "user:read")

    response = _auth(api_client, wrong_scope_token).get(
        url,
        {
            "sso_organization_id": str(org.sso_organization_id),
            "user_global_id": "anything",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_expired_token_is_rejected(api_client, url, service_application, org):
    """An expired token does not authenticate."""

    expired = AccessToken.objects.create(
        user=None,
        application=service_application,
        token=generate_token(),
        scope=MANAGER_CHECK_SCOPE,
        expires=now_in_utc() - timedelta(hours=1),
    )

    response = _auth(api_client, expired).get(
        url,
        {
            "sso_organization_id": str(org.sso_organization_id),
            "user_global_id": "anything",
        },
    )

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"sso_organization_id": "11111111-1111-1111-1111-111111111111"},
        {"user_global_id": "abc"},
    ],
)
def test_missing_parameters_are_a_400(api_client, url, scoped_token, params):
    """Both query parameters are required."""

    response = _auth(api_client, scoped_token).get(url, params)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_malformed_organization_id_is_a_400(api_client, url, scoped_token):
    """A non-UUID sso_organization_id is a 400, not a 500 from the ORM."""

    response = _auth(api_client, scoped_token).get(
        url,
        {"sso_organization_id": "not-a-uuid", "user_global_id": "abc"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
