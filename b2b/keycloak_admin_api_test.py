# ruff: noqa: SLF001
"""Tests for the Keycloak admin API."""

import json
from urllib.parse import urljoin

import faker
import pytest
import requests

from b2b.factories import RealmRepresentationFactory
from b2b.keycloak_admin_api import (
    KeycloakAdminClient,
    KeycloakAdminModel,
    bootstrap_client,
)
from b2b.keycloak_admin_dataclasses import RealmRepresentation

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


def _mocked_admin_client(settings, mocker):
    """
    Return a mocked KeycloakAdminClient instance.

    Args:
    - settings: The Django settings module mock.
    - mocker: The pytest-mock mocker fixture.
    Returns:
    - client: The KeycloakAdminClient instance.
    - mocked_requests_get: The mocked requests.get function.
    - mocked_token_request: The mocked token request function.
    - mocked_openid_config: The mocked OpenID configuration dictionary.
    """

    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = urljoin(
        FAKE.url(),
        f"/realms/{settings.KEYCLOAK_REALM_NAME}/.well-known/openid-configuration",
    )
    settings.KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL = True

    mocked_openid_config = {
        "token_endpoint": FAKE.url(),
    }
    mocked_requests_get = mocker.patch(
        "requests.get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: mocked_openid_config,
        ),
    )
    mocked_token_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.fetch_token",
        return_value={
            "access_token": FAKE.sha256(),
            "expires_in": 300,
            "token_type": "Bearer",
        },
    )

    client = KeycloakAdminClient()
    return client, mocked_requests_get, mocked_token_request, mocked_openid_config


def _faked_response(response_data):
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps(response_data).encode(encoding="utf-8")
    return response


def test_client_init(settings, mocker):
    """Test that the client initializes correctly."""
    client, mocked_requests_get, mocked_token_request, mocked_openid_config = (
        _mocked_admin_client(settings, mocker)
    )

    assert settings.KEYCLOAK_BASE_URL in client.base_url
    assert client._realm == settings.KEYCLOAK_REALM_NAME
    mocked_requests_get.assert_called_once_with(
        settings.KEYCLOAK_DISCOVERY_URL,
        timeout=60,
        verify=not settings.KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL,
    )
    mocked_token_request.assert_called_once_with(
        mocked_openid_config["token_endpoint"],
        grant_type="client_credentials",
    )


def test_client_realmify(settings, mocker):
    """Test that realmify works as expected."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    endpoint = FAKE.word()
    full_endpoint = client.realmify_url(endpoint)

    assert full_endpoint == urljoin(client.base_url, f"{client._realm}/{endpoint}")


def test_client_get_realms(settings, mocker):
    """Test that get_realms works as expected."""

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response([fake_realm.__dict__]),
    )

    response = client.realms()

    mocked_client_request.assert_called_once_with(
        "GET",
        client.base_url,
    )
    assert response == [fake_realm]


def test_client_get_one_realm(settings, mocker):
    """Test that realm (load a single realm) works as expected."""

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response(fake_realm.__dict__),
    )

    response = client.realm(fake_realm.id)

    mocked_client_request.assert_called_once_with(
        "GET",
        urljoin(client.base_url, fake_realm.id),
    )
    assert response == fake_realm


def test_client_list(settings, mocker):
    """Test that the list op works as expected."""

    # In real life, this is not how you retrieve realms.
    # But we just need an 'endpoint' and a 'represnetation' so this is
    # good enough.

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response([fake_realm.__dict__]),
    )

    response = client.list("realms", RealmRepresentation)

    mocked_client_request.assert_called_once_with(
        "GET",
        urljoin(client.base_url, f"{client._realm}/realms"),
        params={},
    )
    assert response == [fake_realm]


def test_client_retrieve(settings, mocker):
    """Test that the retrieve op works as expected."""

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response(fake_realm.__dict__),
    )

    response = client.retrieve(f"realms/{fake_realm.id}", RealmRepresentation)

    mocked_client_request.assert_called_once_with(
        "GET",
        urljoin(client.base_url, f"{client._realm}/realms/{fake_realm.id}"),
        params={},
    )
    assert response == fake_realm


def test_client_create(settings, mocker):
    """Test that the create op works as expected."""

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response(fake_realm.__dict__),
    )

    response = client.create("realms", RealmRepresentation, fake_realm.__dict__)

    mocked_client_request.assert_called_once_with(
        "POST",
        urljoin(client.base_url, f"{client._realm}/realms"),
        json=fake_realm.__dict__,
    )
    assert response == fake_realm


def test_client_save(settings, mocker):
    """Test that the save op works as expected."""

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response(fake_realm.__dict__),
    )

    response = client.save("realms", fake_realm.__dict__)

    mocked_client_request.assert_called_once_with(
        "PUT",
        urljoin(client.base_url, f"{client._realm}/realms"),
        json=fake_realm.__dict__,
    )
    assert response


def test_client_associate(settings, mocker):
    """Test that the associate op works as expected."""

    fake_realm = RealmRepresentationFactory.create()
    fake_uuid = FAKE.uuid4()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response(fake_realm.__dict__),
    )

    response = client.associate(f"realms/{fake_realm.id}/members", fake_uuid)

    mocked_client_request.assert_called_once_with(
        "POST",
        urljoin(client.base_url, f"{client._realm}/realms/{fake_realm.id}/members"),
        data=fake_uuid,
    )
    assert response


def test_client_disassociate(settings, mocker):
    """Test that the disassociate op works as expected."""

    fake_realm = RealmRepresentationFactory.create()
    fake_uuid = FAKE.uuid4()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response(fake_realm.__dict__),
    )

    response = client.disassociate(f"realms/{fake_realm.id}/members/{fake_uuid}")

    mocked_client_request.assert_called_once_with(
        "DELETE",
        urljoin(
            client.base_url,
            f"{client._realm}/realms/{fake_realm.id}/members/{fake_uuid}",
        ),
    )
    assert response


def test_admin_model(settings, mocker):
    """Test the KeycloakAdminModel class."""

    fake_realm = RealmRepresentationFactory.create()
    fake_uuid = FAKE.uuid4()
    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_list = mocker.patch.object(client, "list", return_value=[fake_realm])
    mocked_get = mocker.patch.object(client, "retrieve", return_value=fake_realm)
    mocked_associate = mocker.patch.object(client, "associate", return_value=True)
    mocked_disassociate = mocker.patch.object(client, "disassociate", return_value=True)

    realm_client = KeycloakAdminModel(client, RealmRepresentation, "realms")

    assert realm_client.list() == [fake_realm]
    assert realm_client.get(fake_realm.id) == fake_realm
    assert realm_client.associate("members", fake_realm.id, fake_uuid) is True
    assert realm_client.disassociate("members", fake_realm.id, fake_uuid) is True

    mocked_list.assert_called_once_with("realms", RealmRepresentation)
    mocked_get.assert_called_once_with(f"realms/{fake_realm.id}", RealmRepresentation)
    mocked_associate.assert_called_once_with(
        f"realms/{fake_realm.id}/members", fake_uuid
    )
    mocked_disassociate.assert_called_once_with(
        f"realms/{fake_realm.id}/members/{fake_uuid}"
    )


@pytest.mark.parametrize(
    "verify_realm",
    [
        True,
        False,
    ],
)
def test_bootstrap_client(settings, mocker, verify_realm):
    """Test that the bootstrap_client helper works as expected."""

    fake_realm = RealmRepresentationFactory.create()

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response([fake_realm.__dict__]),
    )
    settings.KEYCLOAK_REALM_NAME = fake_realm.realm

    assert bootstrap_client(verify_realm=verify_realm)

    if verify_realm:
        mocked_client_request.assert_called()
