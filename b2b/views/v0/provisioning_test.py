"""Tests for the staff-only B2B provisioning API's HTTP surface."""

import faker
import pytest
from django.urls import reverse
from requests.exceptions import HTTPError
from rest_framework import status

from b2b.constants import (
    IDP_PROTOCOL_SAML,
    IDP_STATE_ACTIVE,
    IDP_STATE_DRAFT,
    IDP_STATE_TESTING,
    ONBOARDING_STATE_LIVE,
)
from b2b.exceptions import AliasCollisionError
from b2b.factories import OrganizationIndexPageFactory, OrganizationPageFactory
from b2b.keycloak_admin_dataclasses import (
    OrganizationDomainRepresentation,
    OrganizationRepresentation,
)
from b2b.models import OrganizationIdentityProvider, OrganizationPage

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


@pytest.fixture(autouse=True)
def organization_index():
    """The index page organizations are added under."""

    return OrganizationIndexPageFactory.create()


@pytest.fixture(autouse=True)
def mocked_connection(mocker):
    """
    Stop the views bootstrapping a real Keycloak client.

    The views construct a KeycloakConnection and hand it to the provisioning
    functions, so patching the class covers both.
    """

    connection = mocker.Mock()
    connection.organizations.get.return_value = OrganizationRepresentation(
        id=str(FAKE.uuid4()),
        name="Example University",
        alias="EXAMPLEU",
        redirect_url="https://learn.mit.edu/dashboard/organization/exampleu",
        domains=[OrganizationDomainRepresentation(name="example.edu", verified=True)],
    )
    for target in (
        "b2b.views.v0.provisioning.KeycloakConnection",
        "b2b.provisioning.KeycloakConnection",
    ):
        mocker.patch(target, return_value=connection)
    return connection


def _organizations_url():
    return reverse("b2b:b2b-provisioning-organization-list")


def _organization_url(org_key):
    return reverse(
        "b2b:b2b-provisioning-organization-detail", kwargs={"org_key": org_key}
    )


def _identity_providers_url(org_key):
    return reverse(
        "b2b:b2b-provisioning-organization-idp-list",
        kwargs={"parent_lookup_organization__org_key": org_key},
    )


def _identity_provider_url(org_key, alias, suffix="detail"):
    return reverse(
        f"b2b:b2b-provisioning-organization-idp-{suffix}",
        kwargs={
            "parent_lookup_organization__org_key": org_key,
            "alias": alias,
        },
    )


CREATE_BODY = {
    "name": "Example University",
    "org_key": "EXAMPLEU",
    "domains": ["example.edu"],
    "redirect_url": "https://learn.mit.edu/dashboard/organization/exampleu",
}


def test_create_organization_requires_staff(user_drf_client):
    """
    An org manager is a customer-side role and must not provision.

    IsAdminOrReadOnly grants write to is_staff only; a plain authenticated user
    gets read access and nothing else.
    """

    response = user_drf_client.post(_organizations_url(), CREATE_BODY, format="json")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not OrganizationPage.objects.filter(org_key="EXAMPLEU").exists()


def test_create_organization(admin_drf_client, mocker):
    """A staff create returns 201 and the organization it made."""

    organization = OrganizationPageFactory.build(org_key="EXAMPLEU")
    mocker.patch(
        "b2b.views.v0.provisioning.create_organization",
        return_value=OrganizationPageFactory.create(org_key="EXAMPLEU"),
    )

    response = admin_drf_client.post(_organizations_url(), CREATE_BODY, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["org_key"] == organization.org_key


def test_create_organization_alias_collision_is_a_conflict(admin_drf_client, mocker):
    """A taken alias is 409 with the reason, not a 500."""

    mocker.patch(
        "b2b.views.v0.provisioning.create_organization",
        side_effect=AliasCollisionError("taken"),
    )

    response = admin_drf_client.post(_organizations_url(), CREATE_BODY, format="json")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "taken"


def test_keycloak_failure_is_a_bad_gateway(admin_drf_client, mocker):
    """
    A failed Keycloak call is 502, not 500.

    Our records are intact and the operator's next move is to retry, not to
    open a ticket against MITx Online.
    """

    mocker.patch(
        "b2b.views.v0.provisioning.create_organization",
        side_effect=HTTPError("keycloak said no"),
    )

    response = admin_drf_client.post(_organizations_url(), CREATE_BODY, format="json")

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


def test_retrieve_organization_includes_what_keycloak_holds(admin_drf_client):
    """Domains and the redirect URL live only in Keycloak, so read them back."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")

    response = admin_drf_client.get(_organization_url(organization.org_key))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["domains"] == ["example.edu"]
    assert (
        response.json()["redirect_url"]
        == "https://learn.mit.edu/dashboard/organization/exampleu"
    )


def test_patch_rejects_an_org_key_change(admin_drf_client):
    """
    org_key is immutable, and saying so beats accepting and ignoring it.

    It is part of every B2B courseware ID via create_contract_run_key, which is
    also why reconcile_single_keycloak_org refuses to update it.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")

    response = admin_drf_client.patch(
        _organization_url(organization.org_key),
        {"name": "Renamed", "org_key": "SOMETHINGELSE"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "org_key" in response.json()["errors"]

    organization.refresh_from_db()
    assert organization.org_key == "EXAMPLEU"
    assert organization.name != "Renamed"


def test_patch_updates_the_mutable_fields(admin_drf_client, mocker):
    """name, description, redirect_url and domains are all updatable."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    mocked_update = mocker.patch(
        "b2b.views.v0.provisioning.update_organization", return_value=organization
    )

    response = admin_drf_client.patch(
        _organization_url(organization.org_key),
        {"name": "Renamed", "domains": ["renamed.edu"]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert mocked_update.call_args.kwargs["name"] == "Renamed"
    assert mocked_update.call_args.kwargs["domains"] == ["renamed.edu"]


def test_set_onboarding_state(admin_drf_client):
    """The onboarding record is how an operator says where a customer is."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")

    response = admin_drf_client.post(
        reverse(
            "b2b:b2b-provisioning-organization-onboarding",
            kwargs={"org_key": organization.org_key},
        ),
        {"state": ONBOARDING_STATE_LIVE, "notes": "first cohort enrolled"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["state"] == ONBOARDING_STATE_LIVE

    organization.refresh_from_db()
    assert organization.onboarding.notes == "first cohort enrolled"


def _identity_provider(organization, alias="exampleu", state=IDP_STATE_DRAFT):
    return OrganizationIdentityProvider.objects.create(
        organization=organization,
        alias=alias,
        protocol=IDP_PROTOCOL_SAML,
        lifecycle_state=state,
        metadata_source="https://idp.example.edu/metadata.xml",
        metadata_artifact={"idpEntityId": "https://idp.example.edu/entity"},
    )


def test_identity_providers_are_scoped_to_their_organization(admin_drf_client):
    """The nested route lists only that organization's providers."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)
    _identity_provider(OrganizationPageFactory.create(org_key="OTHERU"), alias="otheru")

    response = admin_drf_client.get(_identity_providers_url(organization.org_key))

    assert response.status_code == status.HTTP_200_OK
    assert [idp["alias"] for idp in response.json()] == ["exampleu"]


def test_listing_providers_for_an_unknown_organization_is_a_404(admin_drf_client):
    """
    An unknown org_key is a 404, not an empty list.

    A mistyped key otherwise reads as "this organization has no identity
    providers", which is a much worse thing for an operator to act on.
    """

    response = admin_drf_client.get(_identity_providers_url("NOSUCHORG"))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_identity_provider_requires_a_metadata_source(admin_drf_client):
    """A SAML IdP takes exactly one of metadata_url or metadata_xml."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")

    response = admin_drf_client.post(
        _identity_providers_url(organization.org_key),
        {
            "alias": "exampleu",
            "protocol": IDP_PROTOCOL_SAML,
            "attribute_map": {"email": "E-Mail Address"},
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_identity_provider(admin_drf_client, mocker):
    """A staff create returns 201 and the provider record."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    mocker.patch(
        "b2b.views.v0.provisioning.create_identity_provider",
        return_value=_identity_provider(organization),
    )

    response = admin_drf_client.post(
        _identity_providers_url(organization.org_key),
        {
            "alias": "exampleu",
            "protocol": IDP_PROTOCOL_SAML,
            "metadata_url": "https://idp.example.edu/metadata.xml",
            "attribute_map": {"email": "E-Mail Address"},
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["lifecycle_state"] == IDP_STATE_DRAFT


def test_transition_rejects_skipping_testing(admin_drf_client):
    """Draft -> active is a 400: an IdP goes live only after a real login."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    identity_provider = _identity_provider(organization)

    response = admin_drf_client.post(
        _identity_provider_url(organization.org_key, "exampleu", suffix="transition"),
        {"state": IDP_STATE_ACTIVE},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST

    identity_provider.refresh_from_db()
    assert identity_provider.lifecycle_state == IDP_STATE_DRAFT


def test_transition_to_testing(admin_drf_client, mocker):
    """The allowed move writes both systems through the provisioning layer."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    identity_provider = _identity_provider(organization)
    mocked_transition = mocker.patch(
        "b2b.views.v0.provisioning.transition_identity_provider",
        return_value=identity_provider,
    )

    response = admin_drf_client.post(
        _identity_provider_url(organization.org_key, "exampleu", suffix="transition"),
        {"state": IDP_STATE_TESTING},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert mocked_transition.call_args.args[1] == IDP_STATE_TESTING


def test_parse_metadata_creates_nothing(admin_drf_client, mocker):
    """The cheapest useful call: see what Keycloak makes of the metadata."""

    config = {"idpEntityId": "https://idp.example.edu/entity"}
    mocker.patch(
        "b2b.views.v0.provisioning.parse_identity_provider_metadata",
        return_value=config,
    )

    response = admin_drf_client.post(
        reverse("b2b:b2b-provisioning-parse-metadata-list"),
        {
            "protocol": IDP_PROTOCOL_SAML,
            "metadata_url": "https://idp.example.edu/metadata.xml",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == config
    assert not OrganizationIdentityProvider.objects.exists()


def test_parse_metadata_is_staff_only(user_drf_client):
    """
    Keycloak fetches a caller-supplied URL here, so this stays staff-only.

    Exposing it to partners needs an allowlist or deny-private-ranges policy
    and a rate limit, which belongs to C2's threat model.
    """

    response = user_drf_client.post(
        reverse("b2b:b2b-provisioning-parse-metadata-list"),
        {
            "protocol": IDP_PROTOCOL_SAML,
            "metadata_url": "http://169.254.169.254/latest/meta-data/",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
