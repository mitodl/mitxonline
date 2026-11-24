"""Tests for the APISIX remote user backend with organization support."""

import base64
import json

import pytest
from django.contrib.auth import SESSION_KEY
from django.test import RequestFactory

from authentication.backends.apisix_remote_user_org import (
    ApisixRemoteUserOrgBackend,
    decode_id_token_header,
    get_session_auth_time,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def _b64json(data, *, urlsafe=False):
    """Base64-encode some data as JSON."""

    encoder = base64.urlsafe_b64encode if urlsafe else base64.b64encode
    return encoder(json.dumps(data).encode()).decode()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        # APISIX format: base64-encoded JSON claims
        (_b64json({"auth_time": 100, "iat": 200}), {"auth_time": 100, "iat": 200}),
        # Raw JWT, unpadded URL-safe payload
        (
            f"{_b64json({'alg': 'none'}, urlsafe=True).rstrip('=')}."
            f"{_b64json({'iat': 200}, urlsafe=True).rstrip('=')}.sig",
            {"iat": 200},
        ),
        ("not base64 at all!", None),
        (_b64json(["not", "a", "dict"]), None),
        (None, None),
    ],
)
def test_decode_id_token_header(header, expected):
    """Test that we can read the claims out of the X-ID-Token header."""

    headers = {"HTTP_X_ID_TOKEN": header} if header is not None else {}
    request = RequestFactory().get("/", **headers)

    assert decode_id_token_header(request) == expected


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ({"auth_time": 100, "iat": 200}, 100),
        ({"iat": 200}, 200),
        ({"sid": "abc"}, None),
        ({"auth_time": "garbage"}, None),
    ],
)
def test_get_session_auth_time(claims, expected):
    """Test that we prefer auth_time and fall back to iat."""

    request = RequestFactory().get("/", HTTP_X_ID_TOKEN=_b64json(claims))

    assert get_session_auth_time(request) == expected


@pytest.mark.parametrize("has_id_token", [True, False])
def test_configure_user_reconciles_orgs(mocker, has_id_token):
    """Test that configure_user passes the orgs and session auth time along."""

    user = UserFactory.create()
    org_id = "6c1a3d9e-2b55-4c4e-9f0a-2d7c2f5a1b11"
    userinfo = {
        "sub": str(user.global_id),
        "preferred_username": user.username,
        "email": user.email,
        "name": user.name,
        "organization": {"Some Org": {"id": org_id}},
    }
    headers = {"HTTP_X_USERINFO": _b64json(userinfo)}

    if has_id_token:
        headers["HTTP_X_ID_TOKEN"] = _b64json({"auth_time": 12345, "iat": 23456})

    mocked_reconcile = mocker.patch(
        "authentication.backends.apisix_remote_user_org.reconcile_user_orgs"
    )
    request = RequestFactory().get("/", **headers)

    ApisixRemoteUserOrgBackend().configure_user(request, user, created=False)

    mocked_reconcile.assert_called_once_with(
        user, [org_id], session_auth_time=12345 if has_id_token else None
    )


CURRENT_USER_URL = "/api/v0/users/current_user/"


def _userinfo_header(user):
    """Build the X-Userinfo header APISIX sends for a user."""

    return _b64json(
        {
            "sub": str(user.global_id),
            "preferred_username": user.username,
            "email": user.email,
            "name": user.name,
        }
    )


@pytest.fixture
def gateway_client(settings, client):
    """A test client with the API gateway middleware turned on."""

    settings.MITOL_APIGATEWAY_DISABLE_MIDDLEWARE = False
    return client


def test_gateway_keeps_session_for_same_user(settings, mocker, gateway_client):
    """
    Test that repeat requests from the same gateway user keep the session.

    USERNAME_FIELD is username while the gateway matches on global_id, so
    without the library's same-user check every request would log the user
    out and back in, flushing the session and rewriting last_login.
    """

    mocked_reconcile = mocker.patch(
        "authentication.backends.apisix_remote_user_org.reconcile_user_orgs"
    )
    user = UserFactory.create()
    headers = {"HTTP_X_USERINFO": _userinfo_header(user)}

    first = gateway_client.get(CURRENT_USER_URL, **headers)
    assert first.json()["id"] == user.id
    session_cookie = gateway_client.cookies[settings.SESSION_COOKIE_NAME].value
    user.refresh_from_db()
    last_login = user.last_login

    second = gateway_client.get(CURRENT_USER_URL, **headers)

    assert second.json()["id"] == user.id
    assert settings.SESSION_COOKIE_NAME not in second.cookies
    assert gateway_client.cookies[settings.SESSION_COOKIE_NAME].value == session_cookie
    user.refresh_from_db()
    assert user.last_login == last_login
    # configure_user still runs mid-session, so org membership keeps syncing
    assert mocked_reconcile.call_count == 2


def test_gateway_replaces_session_for_different_user(mocker, gateway_client):
    """Test that a different gateway user replaces the existing session."""

    mocker.patch("authentication.backends.apisix_remote_user_org.reconcile_user_orgs")
    first_user, second_user = UserFactory.create_batch(2)

    gateway_client.get(CURRENT_USER_URL, HTTP_X_USERINFO=_userinfo_header(first_user))
    assert gateway_client.session[SESSION_KEY] == str(first_user.pk)

    response = gateway_client.get(
        CURRENT_USER_URL, HTTP_X_USERINFO=_userinfo_header(second_user)
    )

    assert response.json()["id"] == second_user.id
    assert gateway_client.session[SESSION_KEY] == str(second_user.pk)
