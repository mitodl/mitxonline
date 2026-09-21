"""Tests for the staff-only B2B provisioning API's HTTP surface."""

import faker
import pytest
from django.urls import reverse
from requests.exceptions import HTTPError
from rest_framework import status
from rest_framework.test import APIClient

from b2b.constants import (
    IDP_PROTOCOL_OIDC,
    IDP_PROTOCOL_SAML,
    IDP_STATE_ACTIVE,
    IDP_STATE_DRAFT,
    IDP_STATE_TESTING,
    ONBOARDING_STATE_LIVE,
    ONBOARDING_STATE_ORG_CREATED,
    PROVISIONING_ACTION_ONBOARDING_CHANGED,
)
from b2b.exceptions import AliasCollisionError, OrganizationNameCollisionError
from b2b.factories import OrganizationIndexPageFactory, OrganizationPageFactory
from b2b.keycloak_admin_dataclasses import (
    OrganizationDomainRepresentation,
    OrganizationRepresentation,
)
from b2b.models import (
    OrganizationIdentityProvider,
    OrganizationOnboarding,
    OrganizationPage,
    OrganizationProvisioningAudit,
)
from b2b.provisioning import set_onboarding_state

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


def test_create_organization_name_collision_is_a_conflict(admin_drf_client, mocker):
    """A name whose page slug is taken is 409, not the 500 in MITXONLINE-73J."""

    mocker.patch(
        "b2b.views.v0.provisioning.create_organization",
        side_effect=OrganizationNameCollisionError("name taken"),
    )

    response = admin_drf_client.post(_organizations_url(), CREATE_BODY, format="json")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "name taken"


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


def test_patching_an_unprovisioned_organization_is_a_conflict(admin_drf_client):
    """
    An org with no Keycloak record is 409, not 502.

    502 would say the Keycloak API failed. It did not - our record is the
    incomplete one, and retrying will never fix it. Roughly 24 production
    organizations are in this state (hq#10552).
    """

    organization = OrganizationPageFactory.create(
        org_key="LEGACYU", sso_organization_id=None
    )

    response = admin_drf_client.patch(
        _organization_url(organization.org_key),
        {"name": "Renamed"},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "LEGACYU" in response.json()["detail"]


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


def test_saml_identity_provider_requires_attribute_mappers(admin_drf_client):
    """
    Nothing maps a SAML assertion's attributes onto the user unless we say so.

    A SAML IdP with no mappers brokers users with no email or name, which is a
    support ticket rather than a working integration.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")

    response = admin_drf_client.post(
        _identity_providers_url(organization.org_key),
        {
            "alias": "exampleu",
            "protocol": IDP_PROTOCOL_SAML,
            "metadata_url": "https://idp.example.edu/metadata.xml",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_oidc_identity_provider_does_not_require_attribute_mappers(
    admin_drf_client, mocker
):
    """
    OIDC providers are valid with no mappers, and ours run that way.

    ol-infrastructure's onboard_oidc_org creates no attribute-importer mappers
    at all, so every OIDC IdP Pulumi manages in production today has none.
    Rejecting that configuration would refuse what we already run.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    mocked_create = mocker.patch(
        "b2b.views.v0.provisioning.create_identity_provider",
        return_value=_identity_provider(organization),
    )

    response = admin_drf_client.post(
        _identity_providers_url(organization.org_key),
        {
            "alias": "exampleu",
            "protocol": IDP_PROTOCOL_OIDC,
            "discovery_url": "https://idp.example.edu/.well-known/openid-configuration",
            "client_id": "mitxonline",
            "client_secret": "shh",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    mocked_create.assert_called_once()


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


def test_patch_identity_provider_is_staff_only(user_drf_client):
    """A non-staff user cannot edit a partner's SSO configuration."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = user_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"),
        {"display_name": "Example U"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_patch_identity_provider(admin_drf_client, mocker):
    """An edit goes through the provisioning layer and returns the record."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    identity_provider = _identity_provider(organization)
    mocked_update = mocker.patch(
        "b2b.views.v0.provisioning.update_identity_provider",
        return_value=identity_provider,
    )

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"),
        {
            "display_name": "Example U",
            "attribute_map": {"email": "E-Mail Address"},
            "attribute_name_map": {},
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert mocked_update.call_args.kwargs == {
        "display_name": "Example U",
        "attribute_map": {"email": "E-Mail Address"},
        "attribute_name_map": {},
    }


def test_patch_identity_provider_refuses_one_saml_map_alone(admin_drf_client, mocker):
    """
    One map alone would delete the other's mappers.

    SAML splits its mappers across friendly names and attribute names, and the
    pair replaces the whole set, so an operator fixing one mapping must say
    what the other holds rather than discover it emptied.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)
    mocked_update = mocker.patch("b2b.views.v0.provisioning.update_identity_provider")

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"),
        {"attribute_map": {"email": "E-Mail Address"}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "attribute_name_map" in response.json()["errors"]
    mocked_update.assert_not_called()


def test_patch_identity_provider_takes_a_discovery_url_for_oidc(
    admin_drf_client, mocker
):
    """OIDC names its metadata source discovery_url; the saga takes one source."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    identity_provider = OrganizationIdentityProvider.objects.create(
        organization=organization,
        alias="exampleu-oidc",
        protocol=IDP_PROTOCOL_OIDC,
        lifecycle_state=IDP_STATE_ACTIVE,
        metadata_source="https://idp.example.edu/.well-known/openid-configuration",
    )
    mocked_update = mocker.patch(
        "b2b.views.v0.provisioning.update_identity_provider",
        return_value=identity_provider,
    )

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu-oidc"),
        {"discovery_url": "https://idp.example.edu/.well-known/openid-configuration2"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert mocked_update.call_args.kwargs == {
        "metadata_url": "https://idp.example.edu/.well-known/openid-configuration2"
    }


def test_patch_identity_provider_rejects_an_alias_change(admin_drf_client):
    """
    The alias is rejected rather than ignored.

    Keycloak refuses to change it, and the only other way to get a new alias is
    delete and recreate, which unlinks every user brokered through the IdP.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"),
        {"alias": "exampleu-2"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "alias" in response.json()["errors"]


def test_patch_identity_provider_rejects_oidc_fields_on_a_saml_provider(
    admin_drf_client,
):
    """A client secret on a SAML IdP would sit in its config unread."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"),
        {"client_id": "mitxonline", "client_secret": "shh"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_patch_identity_provider_rejects_a_blank_secret(admin_drf_client, mocker):
    """
    A blank client secret is an empty form field, not an instruction.

    Writing it through would leave the partner's IdP with no secret and their
    logins failing. Creation refuses the same input.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    OrganizationIdentityProvider.objects.create(
        organization=organization,
        alias="exampleu-oidc",
        protocol=IDP_PROTOCOL_OIDC,
        lifecycle_state=IDP_STATE_ACTIVE,
        metadata_source="https://idp.example.edu/.well-known/openid-configuration",
    )
    mocked_update = mocker.patch("b2b.views.v0.provisioning.update_identity_provider")

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu-oidc"),
        {"client_secret": ""},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    mocked_update.assert_not_called()


def test_patch_identity_provider_refuses_to_clear_saml_mappers(admin_drf_client):
    """
    A SAML IdP with no mappers brokers users with no email or name.

    The maps replace the whole mapper set, so an edit that leaves both empty
    would do exactly what creation refuses to do.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"),
        {"attribute_map": {}, "attribute_name_map": {}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_patch_identity_provider_rejects_an_empty_body(admin_drf_client):
    """Nothing to change is a mistake worth reporting, not a no-op 200."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = admin_drf_client.patch(
        _identity_provider_url(organization.org_key, "exampleu"), {}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


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


@pytest.fixture
def staff_drf_client(staff_user):
    """A DRF client for an is_staff user who is not a superuser."""

    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


def _events_url(org_key):
    return reverse(
        "b2b:b2b-provisioning-organization-events", kwargs={"org_key": org_key}
    )


@pytest.mark.parametrize(
    "url",
    [
        lambda _organization: _organizations_url(),
        lambda organization: _organization_url(organization.org_key),
        lambda organization: _identity_providers_url(organization.org_key),
        lambda organization: _identity_provider_url(organization.org_key, "exampleu"),
        lambda organization: _events_url(organization.org_key),
    ],
)
def test_reads_are_staff_only(user_drf_client, url):
    """
    Partner SSO config is not for any signed-in learner to read.

    The routes were IsAdminOrReadOnly, which let any authenticated user list an
    organization's identity providers and their parsed metadata.
    """

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = user_drf_client.get(url(organization))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_list_organizations(staff_drf_client, mocked_connection):
    """
    The list carries onboarding and IdPs, and does not ask Keycloak per row.

    domains and redirect_url are Keycloak-only, so they are null in the list.
    """

    organization = OrganizationPageFactory.create(name="Example University")
    OrganizationOnboarding.objects.create(
        organization=organization, state=ONBOARDING_STATE_LIVE
    )
    _identity_provider(organization)
    OrganizationPageFactory.create(name="Other University")

    response = staff_drf_client.get(_organizations_url())

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["count"] == 2
    first = body["results"][0]
    assert first["org_key"] == organization.org_key
    assert first["onboarding"]["state"] == ONBOARDING_STATE_LIVE
    assert [idp["alias"] for idp in first["identity_providers"]] == ["exampleu"]
    assert first["domains"] is None
    assert first["redirect_url"] is None
    assert body["results"][1]["onboarding"] is None
    mocked_connection.organizations.get.assert_not_called()


def test_list_organizations_query_count_does_not_grow_with_rows(
    staff_drf_client, django_assert_num_queries
):
    """Onboarding and IdPs are joined and prefetched, not fetched per row."""

    for index in range(5):
        organization = OrganizationPageFactory.create(name=f"University {index}")
        OrganizationOnboarding.objects.create(organization=organization)
        _identity_provider(organization, alias=f"idp-{index}")

    # The request's django_site lookup, the count, the page with its onboarding
    # joined, and the IdP prefetch.
    with django_assert_num_queries(4):
        response = staff_drf_client.get(_organizations_url())

    assert response.json()["count"] == 5


def test_list_organizations_paginates_with_the_refine_params(staff_drf_client):
    """The staff dashboard sends o (offset) and l (limit)."""

    for index in range(3):
        OrganizationPageFactory.create(name=f"University {index}")

    response = staff_drf_client.get(_organizations_url(), {"o": 1, "l": 1})

    body = response.json()
    assert body["count"] == 3
    assert [org["name"] for org in body["results"]] == ["University 1"]


@pytest.mark.parametrize("q", ["exam", "EXAMPLEU", "exampleu"])
def test_list_organizations_searches_name_and_org_key(staff_drf_client, q):
    """Q matches the name or the org key, case-insensitively."""

    OrganizationPageFactory.create(name="Example University", org_key="EXAMPLEU")
    OrganizationPageFactory.create(name="Other University", org_key="OTHERU")

    response = staff_drf_client.get(_organizations_url(), {"q": q})

    assert [org["org_key"] for org in response.json()["results"]] == ["EXAMPLEU"]


def test_list_organizations_filters_on_onboarding_state(staff_drf_client):
    """The "what is left" view: organizations at a given stage."""

    live = OrganizationPageFactory.create(name="Live University")
    OrganizationOnboarding.objects.create(
        organization=live, state=ONBOARDING_STATE_LIVE
    )
    OrganizationPageFactory.create(name="Pending University")

    response = staff_drf_client.get(
        _organizations_url(), {"onboarding_state": ONBOARDING_STATE_LIVE}
    )

    assert [org["org_key"] for org in response.json()["results"]] == [live.org_key]


def test_identity_provider_includes_the_service_provider_details(
    staff_drf_client, settings
):
    """An operator hands the partner these, so the API serves them."""

    settings.KEYCLOAK_BASE_URL = "https://sso.example.mit.edu"
    settings.KEYCLOAK_REALM_NAME = "olapps"
    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    _identity_provider(organization)

    response = staff_drf_client.get(
        _identity_provider_url(organization.org_key, "exampleu")
    )

    assert response.json()["service_provider"] == {
        "entity_id": "https://sso.example.mit.edu/realms/olapps",
        "redirect_uri": "https://sso.example.mit.edu/realms/olapps/broker/exampleu/endpoint",
        "metadata_url": "https://sso.example.mit.edu/realms/olapps/broker/exampleu/endpoint/descriptor",
    }


def test_set_onboarding_state_records_who_did_it(staff_drf_client, staff_user):
    """The view passes the requesting user through to the audit trail."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")

    staff_drf_client.post(
        reverse(
            "b2b:b2b-provisioning-organization-onboarding",
            kwargs={"org_key": organization.org_key},
        ),
        {"state": ONBOARDING_STATE_LIVE},
        format="json",
    )

    audit = OrganizationProvisioningAudit.objects.get(organization=organization)
    assert audit.acting_user == staff_user
    assert audit.action == PROVISIONING_ACTION_ONBOARDING_CHANGED


def test_transition_passes_the_actor(staff_drf_client, staff_user, mocker):
    """Every write route hands the requesting user to the service function."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    identity_provider = _identity_provider(organization, state=IDP_STATE_TESTING)
    mocked_transition = mocker.patch(
        "b2b.views.v0.provisioning.transition_identity_provider",
        return_value=identity_provider,
    )

    staff_drf_client.post(
        _identity_provider_url(organization.org_key, "exampleu", suffix="transition"),
        {"state": IDP_STATE_ACTIVE},
        format="json",
    )

    assert mocked_transition.call_args.kwargs["actor"] == staff_user


def test_events_are_newest_first_and_paginated(staff_drf_client, staff_user):
    """The review trail for an organization, most recent change on top."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    for state in (ONBOARDING_STATE_ORG_CREATED, ONBOARDING_STATE_LIVE):
        set_onboarding_state(organization, state, actor=staff_user)
    set_onboarding_state(
        OrganizationPageFactory.create(org_key="OTHERU"), ONBOARDING_STATE_LIVE
    )

    response = staff_drf_client.get(_events_url(organization.org_key), {"l": 1})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["count"] == 2
    (event,) = body["results"]
    assert event["action"] == PROVISIONING_ACTION_ONBOARDING_CHANGED
    assert event["data_after"]["state"] == ONBOARDING_STATE_LIVE
    assert event["actor"] == {
        "id": staff_user.id,
        "username": staff_user.username,
        "email": staff_user.email,
    }
    assert set(event) == {
        "id",
        "action",
        "identity_provider_alias",
        "actor",
        "data_before",
        "data_after",
        "created_on",
    }


def test_events_for_a_system_change_have_no_actor(staff_drf_client):
    """A change with no requesting user (a command, a task) has a null actor."""

    organization = OrganizationPageFactory.create(org_key="EXAMPLEU")
    set_onboarding_state(organization, ONBOARDING_STATE_LIVE)

    response = staff_drf_client.get(_events_url(organization.org_key))

    assert response.json()["results"][0]["actor"] is None
