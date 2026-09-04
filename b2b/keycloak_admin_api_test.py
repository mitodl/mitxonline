# ruff: noqa: SLF001
"""Tests for the Keycloak admin API."""

import json
from urllib.parse import urljoin

import faker
import pytest
import requests

from b2b.exceptions import KeycloakAdminImproperlyConfiguredError
from b2b.factories import RealmRepresentationFactory
from b2b.keycloak_admin_api import (
    KeycloakAdminClient,
    KeycloakAdminModel,
    bootstrap_client,
    import_identity_provider_config,
)
from b2b.keycloak_admin_dataclasses import (
    IdentityProviderRepresentation,
    RealmRepresentation,
)

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


def test_client_init_missing_base_url(settings):
    """Test that client init raises exception when KEYCLOAK_BASE_URL is missing."""
    settings.KEYCLOAK_BASE_URL = None

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_BASE_URL setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_empty_base_url(settings):
    """Test that client init raises exception when KEYCLOAK_BASE_URL is empty."""
    settings.KEYCLOAK_BASE_URL = ""

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_BASE_URL setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_missing_realm_name(settings):
    """Test that client init raises exception when KEYCLOAK_REALM_NAME is missing."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = None

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_REALM_NAME setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_empty_realm_name(settings):
    """Test that client init raises exception when KEYCLOAK_REALM_NAME is empty."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = ""

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_REALM_NAME setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_missing_discovery_url(settings):
    """Test that client init raises exception when KEYCLOAK_DISCOVERY_URL is missing."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = None

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_DISCOVERY_URL setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_empty_discovery_url(settings):
    """Test that client init raises exception when KEYCLOAK_DISCOVERY_URL is empty."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = ""

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_DISCOVERY_URL setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_missing_client_id(settings):
    """Test that client init raises exception when KEYCLOAK_ADMIN_CLIENT_ID is missing."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = None

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_ADMIN_CLIENT_ID setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_empty_client_id(settings):
    """Test that client init raises exception when KEYCLOAK_ADMIN_CLIENT_ID is empty."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = ""

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_ADMIN_CLIENT_ID setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_missing_client_secret(settings):
    """Test that client init raises exception when KEYCLOAK_ADMIN_CLIENT_SECRET is missing."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = None

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_ADMIN_CLIENT_SECRET setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_empty_client_secret(settings):
    """Test that client init raises exception when KEYCLOAK_ADMIN_CLIENT_SECRET is empty."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = ""

    with pytest.raises(
        KeycloakAdminImproperlyConfiguredError,
        match=r"KEYCLOAK_ADMIN_CLIENT_SECRET setting is not configured\.",
    ):
        KeycloakAdminClient()


def test_client_init_ssl_verification_handling(settings, mocker):
    """Test that SSL verification is handled correctly based on settings."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL = False

    mocked_openid_config = {"token_endpoint": FAKE.url()}
    mocked_requests_get = mocker.patch(
        "requests.get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: mocked_openid_config,
        ),
    )
    mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.fetch_token",
        return_value={
            "access_token": FAKE.sha256(),
            "expires_in": 300,
            "token_type": "Bearer",
        },
    )

    client = KeycloakAdminClient()

    assert client.skip_verify is False
    mocked_requests_get.assert_called_once_with(
        settings.KEYCLOAK_DISCOVERY_URL,
        timeout=60,
        verify=True,
    )


def test_client_init_ssl_verification_disabled(settings, mocker):
    """Test that SSL verification can be disabled."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL = True

    mocked_openid_config = {"token_endpoint": FAKE.url()}
    mocked_requests_get = mocker.patch(
        "requests.get",
        return_value=mocker.Mock(
            status_code=200,
            json=lambda: mocked_openid_config,
        ),
    )
    mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.fetch_token",
        return_value={
            "access_token": FAKE.sha256(),
            "expires_in": 300,
            "token_type": "Bearer",
        },
    )

    client = KeycloakAdminClient()

    assert client.skip_verify is True
    mocked_requests_get.assert_called_once_with(
        settings.KEYCLOAK_DISCOVERY_URL,
        timeout=60,
        verify=False,
    )


def test_client_init_openid_configuration_request_failure(settings, mocker):
    """Test that client init handles OpenID configuration request failure."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()

    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mocker.patch("requests.get", return_value=mock_response)

    with pytest.raises(requests.HTTPError, match="404 Not Found"):
        KeycloakAdminClient()


def test_client_init_base_url_processing(settings, mocker):
    """Test that base URL is properly processed with admin path."""
    base_url = "https://keycloak.example.com"
    expected_admin_url = "https://keycloak.example.com/admin/realms/"

    settings.KEYCLOAK_BASE_URL = base_url
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()

    mocked_openid_config = {"token_endpoint": FAKE.url()}
    mocker.patch(
        "requests.get",
        return_value=mocker.Mock(status_code=200, json=lambda: mocked_openid_config),
    )
    mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.fetch_token",
        return_value={
            "access_token": FAKE.sha256(),
            "expires_in": 300,
            "token_type": "Bearer",
        },
    )

    client = KeycloakAdminClient()

    assert client.base_url == expected_admin_url


def test_client_init_oauth_session_configuration(settings, mocker):
    """Test that OAuth session is properly configured."""
    settings.KEYCLOAK_BASE_URL = FAKE.url()
    settings.KEYCLOAK_REALM_NAME = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_ID = FAKE.word()
    settings.KEYCLOAK_ADMIN_CLIENT_SECRET = FAKE.word()
    settings.KEYCLOAK_DISCOVERY_URL = FAKE.url()
    settings.KEYCLOAK_ADMIN_CLIENT_SCOPES = ["admin", "openid"]

    mocked_openid_config = {"token_endpoint": "https://keycloak.example.com/token"}
    mocker.patch(
        "requests.get",
        return_value=mocker.Mock(status_code=200, json=lambda: mocked_openid_config),
    )

    mock_token = {
        "access_token": FAKE.sha256(),
        "expires_in": 300,
        "token_type": "Bearer",
    }

    mock_oauth_session = mocker.Mock()
    mock_oauth_session.fetch_token.return_value = mock_token

    mock_oauth_session.session = mocker.Mock()

    mock_constructor = mocker.patch(
        "b2b.keycloak_admin_api.OAuth2Session",
        return_value=mock_oauth_session,
    )

    client = KeycloakAdminClient()

    mock_constructor.assert_called_once_with(
        client_id=settings.KEYCLOAK_ADMIN_CLIENT_ID,
        client_secret=settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
        token_endpoint=mocked_openid_config["token_endpoint"],
        scope=settings.KEYCLOAK_ADMIN_CLIENT_SCOPES,
        verify=not client.skip_verify,
    )

    mock_oauth_session.fetch_token.assert_called_once_with(
        mocked_openid_config["token_endpoint"],
        grant_type="client_credentials",
    )

    assert client.token == mock_token
    assert client.oauth_session == mock_oauth_session
    mock_oauth_session.fetch_token.assert_called_once_with(
        mocked_openid_config["token_endpoint"],
        grant_type="client_credentials",
    )

    assert client.token == mock_token
    assert client.oauth_session == mock_oauth_session


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
        json=fake_uuid,
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

    _, _, _, _ = _mocked_admin_client(settings, mocker)

    mocked_client_request = mocker.patch(
        "authlib.integrations.requests_client.OAuth2Session.request",
        return_value=_faked_response([fake_realm.__dict__]),
    )
    settings.KEYCLOAK_REALM_NAME = fake_realm.realm

    assert bootstrap_client(verify_realm=verify_realm)

    if verify_realm:
        mocked_client_request.assert_called()


def test_realm_representation_ignores_extra_fields():
    """Test that RealmRepresentation does not fail when given unknown fields.

    This validates that new fields added to the Keycloak API response will not
    break instantiation of the model.
    """
    fake_realm = RealmRepresentationFactory.create()
    data = fake_realm.__dict__.copy()
    data["brandNewUnknownField"] = "some_value"

    realm = RealmRepresentation(**data)

    assert realm.id == fake_realm.id
    assert realm.realm == fake_realm.realm


def test_create_returning_id_reads_the_location_header(settings, mocker):
    """Keycloak answers a create with 201 and an empty body plus a Location."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    new_id = FAKE.uuid4()
    response = requests.Response()
    response.status_code = 201
    response.headers["Location"] = (
        f"https://keycloak.example.com/admin/realms/olapps/organizations/{new_id}"
    )
    mocker.patch.object(client, "realm_request", return_value=response)

    assert client.create_returning_id("organizations", {"alias": "acme"}) == new_id


def test_create_returning_id_without_a_location(settings, mocker):
    """A create with no Location header returns None rather than guessing."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    response = requests.Response()
    response.status_code = 201
    mocker.patch.object(client, "realm_request", return_value=response)

    assert client.create_returning_id("organizations", {"alias": "acme"}) is None


def test_post_raw_returns_the_body_uncoerced(settings, mocker):
    """import-config answers with a flat config map, not a representation."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    config = {"singleSignOnServiceUrl": FAKE.url(), "idpEntityId": FAKE.url()}
    mocker.patch.object(client, "realm_request", return_value=_faked_response(config))

    assert client.post_raw("identity-provider/import-config", {}) == config


def test_model_list_all_pages_until_exhausted(settings, mocker):
    """
    list_all keeps asking until a short page comes back.

    Keycloak's collection endpoints default to 10 results when `max` is absent,
    so anything that needs the whole collection has to page for it.
    """

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    first_page = RealmRepresentationFactory.create_batch(2)
    second_page = RealmRepresentationFactory.create_batch(1)
    mocked_list = mocker.patch.object(
        client, "list", side_effect=[first_page, second_page]
    )

    realm_model = KeycloakAdminModel(client, RealmRepresentation, "realms")

    assert realm_model.list_all(page_size=2) == [*first_page, *second_page]
    assert mocked_list.call_args_list == [
        mocker.call("realms", RealmRepresentation, first=0, max=2),
        mocker.call("realms", RealmRepresentation, first=2, max=2),
    ]


def test_model_create_update_delete(settings, mocker):
    """The three model-level methods the provisioning API needs."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    fake_alias = FAKE.word()
    mocked_create = mocker.patch.object(
        client, "create_returning_id", return_value=fake_alias
    )
    mocked_save = mocker.patch.object(client, "save", return_value=True)
    mocked_delete = mocker.patch.object(client, "delete", return_value=True)

    idp_model = KeycloakAdminModel(
        client, IdentityProviderRepresentation, "identity-provider/instances"
    )

    assert idp_model.create({"alias": fake_alias}) == fake_alias
    assert idp_model.update(fake_alias, {"enabled": True}) is True
    assert idp_model.delete(fake_alias) is True

    mocked_create.assert_called_once_with(
        "identity-provider/instances", {"alias": fake_alias}
    )
    mocked_save.assert_called_once_with(
        f"identity-provider/instances/{fake_alias}", {"enabled": True}
    )
    mocked_delete.assert_called_once_with(f"identity-provider/instances/{fake_alias}")


def test_import_identity_provider_config_from_url(settings, mocker):
    """The URL form asks Keycloak to fetch and parse the metadata itself."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    config = {"idpEntityId": FAKE.url()}
    mocked_post = mocker.patch.object(client, "post_raw", return_value=config)
    metadata_url = FAKE.url()

    result = import_identity_provider_config(
        "saml", from_url=metadata_url, client=client
    )

    assert result == config
    mocked_post.assert_called_once_with(
        "identity-provider/import-config",
        {"providerId": "saml", "fromUrl": metadata_url},
    )


def test_import_identity_provider_config_from_document(settings, mocker):
    """Metadata supplied inline is uploaded rather than fetched."""

    client, _, _, _ = _mocked_admin_client(settings, mocker)

    config = {"idpEntityId": FAKE.url()}
    mocked_post = mocker.patch.object(client, "post_file", return_value=config)
    metadata = "<EntityDescriptor />"

    result = import_identity_provider_config("saml", metadata=metadata, client=client)

    assert result == config
    mocked_post.assert_called_once_with(
        "identity-provider/import-config",
        {"providerId": "saml"},
        {"file": ("metadata.xml", metadata, "application/xml")},
    )
