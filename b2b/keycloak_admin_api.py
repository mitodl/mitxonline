"""
Code for working with Keycloak

Some data we need that's stored in Keycloak is best retrieved by using its own
API, rather than using SCIM or relying on the OIDC payload. At the moment, this
is mostly the organizations data.
"""

from urllib.parse import urljoin

import requests
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings

from b2b.exceptions import KeycloakAdminImproperlyConfiguredError
from b2b.keycloak_admin_dataclasses import (
    OrganizationRepresentation,
    RealmRepresentation,
    UserRepresentation,
)

KCAM_ORGANIZATIONS = (OrganizationRepresentation, "organizations")
KCAM_USERS = (UserRepresentation, "users")


class KeycloakAdminClient:
    """Client for the Keycloak admin API."""

    base_url = None
    _realm = None
    oauth_session = None
    skip_verify = False

    def __init__(self):
        """
        Configure the client so we can use it.

        These settings must be in place:
        - KEYCLOAK_BASE_URL: The base URL for the Keycloak instance.
        - KEYCLOAK_DISCOVERY_URL: The OpenID discovery URL for the realm.
        - KEYCLOAK_ADMIN_CLIENT_ID: The client ID to use for the admin client.
        - KEYCLOAK_ADMIN_CLIENT_SECRET: The client secret to use for the admin client.
        - KEYCLOAK_REALM_NAME: The realm we are working with.

        If any of these are incorrect or missing, you'll get an
        KeycloakAdminImproperlyConfiguredError.

        The client should be one that has the ability to use the admin API. The
        regular authentication client may not have this permission.
        """

        self.base_url = settings.KEYCLOAK_BASE_URL
        if not self.base_url:
            msg = "KEYCLOAK_BASE_URL setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        self.base_url = urljoin(self.base_url, "/admin/realms/")
        self._realm = settings.KEYCLOAK_REALM_NAME
        if not self._realm:
            msg = "KEYCLOAK_REALM_NAME setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)

        realm_discovery = settings.KEYCLOAK_DISCOVERY_URL
        if not realm_discovery:
            msg = "KEYCLOAK_DISCOVERY_URL setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        client_id = settings.KEYCLOAK_ADMIN_CLIENT_ID
        if not client_id:
            msg = "KEYCLOAK_ADMIN_CLIENT_ID setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)
        client_secret = settings.KEYCLOAK_ADMIN_CLIENT_SECRET
        if not client_secret:
            msg = "KEYCLOAK_ADMIN_CLIENT_SECRET setting is not configured."
            raise KeycloakAdminImproperlyConfiguredError(msg)

        self.skip_verify = settings.KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL or False

        openid_configuration = requests.get(
            realm_discovery,
            timeout=60,
            verify=not self.skip_verify,
        )
        openid_configuration.raise_for_status()
        self.openid_configuration = openid_configuration.json()

        self.oauth_session = OAuth2Session(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint=self.openid_configuration["token_endpoint"],
            scope=settings.KEYCLOAK_ADMIN_CLIENT_SCOPES,
            verify=not self.skip_verify,
        )
        self.token = self.oauth_session.fetch_token(
            self.openid_configuration["token_endpoint"],
            grant_type="client_credentials",
        )

    def realmify_url(self, url_path):
        """
        Prefix the given URL path with the realm base path.

        The admin API URLs are all /admin/realms/ and then _usually_ a realm
        name.

        Args:
        - url_path: The URL path to prefix with the realm base path.
        Returns:
        - The full URL path with the realm base path prefixed.
        """

        return urljoin(self.base_url, f"{self._realm}/{url_path}")

    def _request(self, method, url_path, **kwargs):
        """Perform an HTTP request against the given URL path."""

        return (
            self.oauth_session.request(method, url_path, **kwargs)
            if self.oauth_session
            else None
        )

    def request(self, method, url_path, **kwargs):
        """Perform an HTTP request against the given URL path."""

        request_url = self.realmify_url(url_path)

        return self._request(method, request_url, **kwargs)

    def realm_request(self, method, url_path, **kwargs):
        """Perform an HTTP request against the given URL path, skipping realm prefixing."""

        request_url = urljoin(self.base_url, url_path)

        return self._request(method, request_url, **kwargs)

    def realms(self):
        """
        Get the realms available for this client.

        The realms URLs don't follow the same URL pattern as the rest of the
        APIs. This will only return the realms that the configured client can
        access; there's no other search parameters.

        Returns:
        - List of RealmRepresentation objects
        """

        response = self.realm_request("GET", "")
        response.raise_for_status()
        list_data = response.json()

        return [RealmRepresentation(**item) for item in list_data]

    def realm(self, realm_name):
        """
        Get a single realm by its name.

        Args:
        - realm_name: The name of the realm to retrieve.

        Returns:
        - A single RealmRepresentation object
        """

        response = self.realm_request("GET", realm_name)
        response.raise_for_status()
        item_data = response.json()

        return RealmRepresentation(**item_data)

    def set_realm(self, realm_name):
        """Set the realm name in the client."""

        self._realm = realm_name

    def list(self, endpoint, representation, **kwargs):
        """
        List objects from the endpoint in the realm.

        The keyword args should be whatever is supported by the endpoint itself.
        The general ones listed are generally supported, but you should check
        the API docs for the exact list for the endpoint.

        Args:
        - endpoint: The endpoint to list (e.g., "organizations", "users", etc).
        - representation: The dataclass to use for the representation of each item.
          (e.g. OrganizationRepresentation, etc.)
        General Keyword Args:
        - exact: bool; If True, only return exact matches for the search term
        - search: str; A search term to filter organizations by name or description.
        - q: str; Search by attribute values ("key:value key:value").
        Returns:
        - A list of "representation" type instances.
        """

        response = self.request("GET", endpoint, params=kwargs)
        response.raise_for_status()
        list_data = response.json()

        return [representation(**item) for item in list_data]

    def retrieve(self, endpoint, representation, **kwargs):
        """
        Retrieve an object from the endpoint in the realm.

        Construct the endpoint param as necessary - for example, for a user,
        pass "users/{user_id}".

        Args:
        - endpoint: The endpoint to list (e.g., "organizations", "users", etc).
        - representation: The dataclass to use for the representation of each item.
          (e.g. OrganizationRepresentation, etc.)
        Returns:
        - A single "representation" type instance.
        """

        response = self.request("GET", endpoint, params=kwargs)
        response.raise_for_status()
        list_data = response.json()

        return representation(**list_data)

    def create(self, endpoint, representation, data):
        """
        Create an object at the endpoint in the realm.

        Args:
        - endpoint: The endpoint to use (e.g., "organizations", "users", etc).
        - representation: The dataclass instance to save.
        - data: The data to save.

        Returns:
        - The saved representation instance.
        """

        response = self.request("POST", endpoint, json=data)
        response.raise_for_status()
        item_data = response.json()

        return representation(**item_data)

    def save(self, endpoint, data):
        """
        Create an object at the endpoint in the realm.

        No data is returned - just a status - so we don't need th representation
        class.

        Args:
        - endpoint: The endpoint to use (e.g., "organizations", "users", etc).
        - data: The data to save.

        Returns:
        - True on success
        """

        response = self.request("PUT", endpoint, json=data)
        response.raise_for_status()

        return True

    def associate(self, endpoint, target_id):
        """
        Associate an object at the endpoint in the realm with the target ID.

        For things like adding members to an organization, we don't send the
        entire user object. We just send the user ID to associate. save will
        try to JSONify the data we're sending, which is not necessarily useful
        in this case, so this op is separate.

        Args:
        - endpoint: The endpoint to use (e.g., "organizations/{org_id}/members", etc).
        - target_id: The ID of the object to associate.
        Returns:
        - True if successful.
        Raises:
        - requests.HTTPError if the request fails.
        """

        response = self.request("POST", endpoint, data=target_id)
        response.raise_for_status()

        return True

    def disassociate(self, endpoint):
        """
        Disassociate an object at the endpoint in the realm from the target ID.

        This is the flip side of associate - removing a membership. The API call
        for this is slightly different - we send a DELETE and the target ID is
        sent in the URL.

        Args:
        - endpoint: The endpoint to use (e.g., "organizations/{org_id}/members", etc).
        - target_id: The ID of the object to associate.
        Returns:
        - True if successful.
        Raises:
        - requests.HTTPError if the request fails.
        """

        response = self.request("DELETE", endpoint)
        response.raise_for_status()

        return True


class KeycloakAdminModel:
    """Middleware class to help with working with Keycloak data."""

    admin_client = None
    representation_class = None
    endpoint = None

    def __init__(self, admin_client, representation_class, endpoint):
        """
        Configure the model.

        Args:
        - admin_client: An instance of KeycloakAdminClient.
        - representation_class: The dataclass that we pass in/out of the API.
        - endpoint: The endpoint to use.
        """

        self.admin_client = admin_client
        self.representation_class = representation_class
        self.endpoint = endpoint

    def list(self, **kwargs):
        """
        List all objects in the realm.

        As with the client list method, keyword args should be whatever's
        supported by the API.

        Keyword Args:
        - exact: bool; If True, only return exact matches for the search term
        - search: str; A search term to filter objects by name or description.
        - q: str; Search by attribute values ("key:value key:value").
        Returns:
        - A list of representation instances.
        """

        return self.admin_client.list(
            self.endpoint, self.representation_class, **kwargs
        )

    def get(self, item_id):
        """
        Get a single object by its ID.

        Args:
        - item_id: The ID of the object to retrieve.

        Returns:
        - An instance of representation.
        """

        return self.admin_client.retrieve(
            f"{self.endpoint}/{item_id}",
            self.representation_class,
        )

    def associate(self, association_type, parent_id, child_id):
        """
        Associate the object with the given ID with the target ID.

        Args:
        - association_type: The "type" of association to make (e.g., "members").
        - parent_id: The ID of the object to add the item to.
        - child_id: The ID of the object to add.
        Returns:
        - True if successful.
        Raises:
        - requests.HTTPError if the request fails.
        """

        return self.admin_client.associate(
            f"{self.endpoint}/{parent_id}/{association_type}", child_id
        )

    def disassociate(self, association_type, parent_id, child_id):
        """
        Disassociate the object with the given ID from the target ID.

        Args:
        - association_type: The "type" of association to make (e.g., "members").
        - parent_id: The ID of the object to add the item to.
        - child_id: The ID of the object to add.
        Returns:
        - True if successful.
        Raises:
        - requests.HTTPError if the request fails.
        """

        return self.admin_client.disassociate(
            f"{self.endpoint}/{parent_id}/{association_type}/{child_id}"
        )


def bootstrap_client(*, verify_realm=False):
    """Bootstrap a KeycloakAdminClient instance."""

    client = KeycloakAdminClient()
    target_realm = settings.KEYCLOAK_REALM_NAME

    if verify_realm:
        realms = [realm.realm for realm in client.realms()]
        if target_realm not in realms:
            msg = f"Realm '{target_realm}' not found in Keycloak."
            raise KeycloakAdminImproperlyConfiguredError(msg)

    client.set_realm(target_realm)

    return client


def get_keycloak_model(representation, endpoint, *, client=None):
    """
    Get a KeycloakAdminModel instance for the given model type.

    Use the KCAM_ constants as a shortcut - these are two-tuples of
    (representation_class, endpoint). If a client isn't provided,
    this will bootstrap one.

    Args:
    - representation: The dataclass representation to use.
    - endpoint: The endpoint to use.
    - client: An optional KeycloakAdminClient instance.
    Returns:
    - An instance of KeycloakAdminModel for the given type.
    """

    client = client or bootstrap_client(verify_realm=True)

    return KeycloakAdminModel(client, representation, endpoint)
