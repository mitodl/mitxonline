"""Tests for the staff-only B2B provisioning API's business logic."""

import faker
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db.models import ProtectedError

from b2b.constants import (
    IDP_ALLOWED_TRANSITIONS,
    IDP_LIFECYCLE_CHOICES,
    IDP_PROTOCOL_OIDC,
    IDP_PROTOCOL_SAML,
    IDP_STATE_ACTIVE,
    IDP_STATE_DISABLED,
    IDP_STATE_DRAFT,
    IDP_STATE_TESTING,
    ONBOARDING_STATE_LIVE,
    ONBOARDING_STATE_ORG_CREATED,
    PROVISIONING_ACTION_IDP_CREATED,
    PROVISIONING_ACTION_IDP_DELETED,
    PROVISIONING_ACTION_IDP_METADATA_REFRESHED,
    PROVISIONING_ACTION_IDP_TRANSITIONED,
    PROVISIONING_ACTION_ONBOARDING_CHANGED,
    PROVISIONING_ACTION_ORG_CREATED,
    PROVISIONING_ACTION_ORG_UPDATED,
)
from b2b.exceptions import (
    AliasCollisionError,
    InvalidLifecycleTransitionError,
    OrganizationNameCollisionError,
    OrganizationNotProvisionedError,
    OrphanedKeycloakOrganizationError,
)
from b2b.factories import OrganizationIndexPageFactory, OrganizationPageFactory
from b2b.keycloak_admin_dataclasses import (
    IdentityProviderRepresentation,
    OrganizationDomainRepresentation,
    OrganizationRepresentation,
)
from b2b.models import (
    OrganizationIdentityProvider,
    OrganizationOnboarding,
    OrganizationPage,
    OrganizationProvisioningAudit,
)
from b2b.provisioning import (
    create_identity_provider,
    create_organization,
    delete_identity_provider,
    refresh_identity_provider_metadata,
    set_onboarding_state,
    transition_identity_provider,
    update_organization,
)

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()

PARSED_METADATA = {
    "singleSignOnServiceUrl": "https://idp.example.edu/sso",
    "idpEntityId": "https://idp.example.edu/entity",
}


@pytest.fixture(autouse=True)
def organization_index():
    """
    The index page new OrganizationPages are added under.

    create_organization adds under the existing index rather than calling
    ensure_b2b_organization_index, which would also move every existing
    organization page as a side effect of creating one.
    """

    return OrganizationIndexPageFactory.create()


@pytest.fixture
def connection(mocker):
    """
    A KeycloakConnection whose models are mocks.

    Every provisioning function takes a connection, so the tests never touch
    the network and never need the client bootstrapped.
    """

    fake_connection = mocker.Mock()
    fake_connection.organizations.list_all.return_value = []
    fake_connection.identity_providers.list_all.return_value = []
    fake_connection.organizations.create.return_value = str(FAKE.uuid4())
    fake_connection.identity_providers.create.return_value = str(FAKE.uuid4())
    return fake_connection


@pytest.fixture
def mocked_import_config(mocker):
    """Stand in for Keycloak's metadata parsing."""

    return mocker.patch(
        "b2b.provisioning.import_identity_provider_config",
        return_value=dict(PARSED_METADATA),
    )


def _organization_kwargs(**overrides):
    return {
        "name": "Example University",
        "org_key": "EXAMPLEU",
        "domains": ["example.edu"],
        "description": "",
        "redirect_url": "https://learn.mit.edu/dashboard/organization/exampleu",
        **overrides,
    }


def test_create_organization_writes_both_systems(connection):
    """The happy path: Keycloak first, then our records, alias from org_key."""

    organization = create_organization(connection=connection, **_organization_kwargs())

    keycloak_payload = connection.organizations.create.call_args.args[0]
    assert keycloak_payload["alias"] == "EXAMPLEU"
    assert keycloak_payload["domains"] == [{"name": "example.edu", "verified": True}]

    assert organization.pk is not None
    assert str(organization.sso_organization_id) == str(
        connection.organizations.create.return_value
    )
    assert organization.onboarding.state == ONBOARDING_STATE_ORG_CREATED


def test_create_organization_rejects_a_duplicate_org_key(connection):
    """An org_key already used here is a 409, not a second organization."""

    existing = OrganizationPageFactory.create()

    with pytest.raises(AliasCollisionError):
        create_organization(
            connection=connection, **_organization_kwargs(org_key=existing.org_key)
        )

    connection.organizations.create.assert_not_called()


def test_create_organization_rejects_an_alias_taken_in_the_realm(connection):
    """
    An alias free in our tables can still be taken in the realm.

    The realm is shared with the organizations Pulumi still declares, so
    creating this anyway would break the next pulumi up that declares the
    same name.
    """

    connection.organizations.list_all.return_value = [
        OrganizationRepresentation(id=str(FAKE.uuid4()), alias="exampleu")
    ]

    with pytest.raises(AliasCollisionError):
        create_organization(connection=connection, **_organization_kwargs())

    connection.organizations.create.assert_not_called()


@pytest.mark.parametrize("name", ["Example University", "example university!"])
def test_create_organization_rejects_a_name_that_reuses_a_page_slug(connection, name):
    """
    A name whose slug is taken under the index fails before Keycloak is touched.

    Wagtail's own sibling-slug check in add_child() raises a plain
    ValidationError, which the API turned into a 500 (MITXONLINE-73J), and only
    after a Keycloak organization had been created and had to be deleted again.
    """

    create_organization(connection=connection, **_organization_kwargs())
    connection.organizations.create.reset_mock()

    with pytest.raises(OrganizationNameCollisionError):
        create_organization(
            connection=connection,
            **_organization_kwargs(name=name, org_key="EXAMPLEU2"),
        )

    connection.organizations.create.assert_not_called()
    connection.organizations.delete.assert_not_called()
    assert not OrganizationPage.objects.filter(org_key="EXAMPLEU2").exists()


def test_create_organization_compensates_a_failed_local_write(connection, mocker):
    """
    A failed MITx Online write deletes the Keycloak organization it made.

    A Keycloak org with no MITx Online counterpart is exactly the orphan shape
    the compensation exists to prevent.
    """

    mocker.patch(
        "b2b.provisioning.OrganizationOnboarding.objects.create",
        side_effect=ValueError("no"),
    )

    with pytest.raises(ValueError, match="no"):
        create_organization(connection=connection, **_organization_kwargs())

    connection.organizations.delete.assert_called_once_with(
        connection.organizations.create.return_value
    )
    assert not OrganizationPage.objects.filter(org_key="EXAMPLEU").exists()


def test_create_organization_reports_an_orphan_when_compensation_fails(
    connection, mocker
):
    """
    When the compensating delete also fails, say so and stop.

    Retrying against a system that just failed is worse than logging the orphan
    and letting reconcile_keycloak_orgs adopt it on its next run.
    """

    mocker.patch(
        "b2b.provisioning.OrganizationOnboarding.objects.create",
        side_effect=ValueError("no"),
    )
    connection.organizations.delete.side_effect = ValueError("also no")

    with pytest.raises(OrphanedKeycloakOrganizationError) as failure:
        create_organization(connection=connection, **_organization_kwargs())

    assert str(connection.organizations.create.return_value) in str(failure.value)
    assert not OrganizationPage.objects.filter(org_key="EXAMPLEU").exists()


def test_create_organization_never_leaves_a_null_sso_organization_id(connection):
    """
    An OrganizationPage without sso_organization_id is silently broken.

    attach_user() returns False without doing anything for those, so every
    membership write is a no-op. This is the hq#10552 shape.
    """

    create_organization(connection=connection, **_organization_kwargs())

    assert not OrganizationPage.objects.filter(
        sso_organization_id__isnull=True
    ).exists()


def test_create_organization_refuses_to_write_a_row_without_an_id(connection):
    """
    An unresolvable ID stops the saga rather than writing a null.

    Keycloak sent no Location and the alias lookup found nothing, so there is
    no ID to store and nothing to compensate with either - the delete needs the
    ID we do not have. Writing the row anyway would mint exactly the
    hq#10552 orphan this saga exists to prevent.
    """

    connection.organizations.create.return_value = None
    connection.organizations.list_all.return_value = []

    with pytest.raises(OrphanedKeycloakOrganizationError):
        create_organization(connection=connection, **_organization_kwargs())

    assert not OrganizationPage.objects.filter(org_key="EXAMPLEU").exists()


def test_create_organization_looks_up_the_id_when_keycloak_sends_no_location(
    connection,
):
    """Keycloak's create answers 201 with an empty body; fall back to the alias."""

    known_id = str(FAKE.uuid4())
    connection.organizations.create.return_value = None
    connection.organizations.list_all.return_value = [
        OrganizationRepresentation(id=known_id, alias="EXAMPLEU")
    ]

    # The pre-flight collision check runs against the same list, so start from
    # an alias that is not yet in the realm and add it on the second call.
    connection.organizations.list_all.side_effect = [
        [],
        [OrganizationRepresentation(id=known_id, alias="EXAMPLEU")],
    ]

    organization = create_organization(connection=connection, **_organization_kwargs())

    assert str(organization.sso_organization_id) == known_id


def test_update_organization_replaces_the_keycloak_representation(connection):
    """Keycloak's organization PUT replaces, so read-modify-write."""

    organization = OrganizationPageFactory.create()
    connection.organizations.get.return_value = OrganizationRepresentation(
        id=str(organization.sso_organization_id),
        name=organization.name,
        alias=organization.org_key,
    )

    update_organization(
        organization,
        connection=connection,
        name="Renamed",
        domains=["renamed.edu"],
    )

    _, payload = connection.organizations.update.call_args.args
    assert payload["name"] == "Renamed"
    assert payload["domains"] == [{"name": "renamed.edu", "verified": True}]
    assert payload["alias"] == organization.org_key

    organization.refresh_from_db()
    assert organization.name == "Renamed"


def test_update_organization_refuses_an_unprovisioned_organization(connection):
    """
    An org with no Keycloak record cannot be updated in Keycloak.

    Roughly 24 production organizations are in this state (hq#10552). Without
    the check the GET goes to organizations/None and the operator is told the
    Keycloak API failed, which is a 502 they would retry forever.
    """

    organization = OrganizationPageFactory.create(sso_organization_id=None)

    with pytest.raises(OrganizationNotProvisionedError):
        update_organization(organization, connection=connection, name="Renamed")

    connection.organizations.get.assert_not_called()
    connection.organizations.update.assert_not_called()


def test_create_identity_provider_refuses_an_unprovisioned_organization(
    connection, mocked_import_config
):
    """
    Same guard as update_organization, checked before anything is written.

    Without it the IdP is created in Keycloak and only the org link fails, so
    the compensation deletes an IdP that should never have been made.
    """

    organization = OrganizationPageFactory.create(sso_organization_id=None)

    with pytest.raises(OrganizationNotProvisionedError):
        create_identity_provider(
            organization,
            connection=connection,
            alias="exampleu",
            protocol=IDP_PROTOCOL_SAML,
            metadata_url="https://idp.example.edu/metadata.xml",
            attribute_map={"email": "E-Mail Address"},
        )

    mocked_import_config.assert_not_called()
    connection.identity_providers.create.assert_not_called()
    connection.identity_providers.delete.assert_not_called()


def test_create_identity_provider_starts_in_draft(connection, mocked_import_config):
    """A new IdP is disabled in Keycloak until somebody moves it to testing."""

    organization = OrganizationPageFactory.create()
    metadata_url = "https://idp.example.edu/metadata.xml"

    identity_provider = create_identity_provider(
        organization,
        connection=connection,
        alias="exampleu",
        protocol=IDP_PROTOCOL_SAML,
        display_name="Example University",
        metadata_url=metadata_url,
        attribute_map={"email": "E-Mail Address"},
    )

    payload = connection.identity_providers.create.call_args.args[0]
    assert payload["enabled"] is False
    assert payload["hideOnLogin"] is True
    assert payload["providerId"] == IDP_PROTOCOL_SAML
    assert payload["config"]["metadataDescriptorUrl"] == metadata_url

    connection.organizations.associate.assert_called_once_with(
        "identity-providers", organization.sso_organization_id, "exampleu"
    )

    assert identity_provider.lifecycle_state == IDP_STATE_DRAFT
    assert identity_provider.metadata_artifact == PARSED_METADATA
    assert identity_provider.metadata_source == metadata_url
    mocked_import_config.assert_called_once()


def test_create_identity_provider_creates_attribute_mappers(
    connection,
    mocked_import_config,
):
    """Attribute mappers are created the same shape ol-infrastructure makes."""

    organization = OrganizationPageFactory.create()

    create_identity_provider(
        organization,
        connection=connection,
        alias="exampleu",
        protocol=IDP_PROTOCOL_SAML,
        metadata_url="https://idp.example.edu/metadata.xml",
        attribute_map={"email": "E-Mail Address"},
    )

    endpoint, payload = connection.client.create_returning_id.call_args.args
    assert endpoint == "identity-provider/instances/exampleu/mappers"
    assert payload["identityProviderMapper"] == "saml-user-attribute-idp-mapper"
    assert payload["config"]["attribute.friendly.name"] == "E-Mail Address"
    assert payload["config"]["user.attribute"] == "email"


def test_create_identity_provider_keeps_the_client_secret_out_of_the_artifact(
    connection,
    mocked_import_config,
):
    """
    The OIDC client secret reaches Keycloak but is never persisted.

    metadata_artifact is served back over the API, so it holds what Keycloak
    parsed out of the partner's metadata and nothing else.
    """

    organization = OrganizationPageFactory.create()
    secret = FAKE.password()

    identity_provider = create_identity_provider(
        organization,
        connection=connection,
        alias="exampleu-oidc",
        protocol=IDP_PROTOCOL_OIDC,
        metadata_url="https://idp.example.edu/.well-known/openid-configuration",
        client_id="mitxonline",
        client_secret=secret,
        attribute_map={"email": "email"},
    )

    payload = connection.identity_providers.create.call_args.args[0]
    assert payload["config"]["clientSecret"] == secret
    assert secret not in str(identity_provider.metadata_artifact)


def test_create_identity_provider_rejects_a_realm_alias_collision(
    connection, mocked_import_config
):
    """IdP aliases are realm-wide, so a collision across customers is real."""

    organization = OrganizationPageFactory.create()
    connection.identity_providers.list_all.return_value = [
        IdentityProviderRepresentation(alias="exampleu")
    ]

    with pytest.raises(AliasCollisionError):
        create_identity_provider(
            organization,
            connection=connection,
            alias="exampleu",
            protocol=IDP_PROTOCOL_SAML,
            metadata_url="https://idp.example.edu/metadata.xml",
            attribute_map={"email": "E-Mail Address"},
        )

    connection.identity_providers.create.assert_not_called()
    mocked_import_config.assert_not_called()


def test_create_identity_provider_compensates_a_failed_local_write(
    connection,
    mocked_import_config,
):
    """A failed link or row write deletes the IdP Keycloak just made."""

    organization = OrganizationPageFactory.create()
    connection.organizations.associate.side_effect = ValueError("no")

    with pytest.raises(ValueError, match="no"):
        create_identity_provider(
            organization,
            connection=connection,
            alias="exampleu",
            protocol=IDP_PROTOCOL_SAML,
            metadata_url="https://idp.example.edu/metadata.xml",
            attribute_map={"email": "E-Mail Address"},
        )

    connection.identity_providers.delete.assert_called_once_with("exampleu")
    assert not OrganizationIdentityProvider.objects.filter(alias="exampleu").exists()


def _identity_provider(organization, state=IDP_STATE_DRAFT):
    return OrganizationIdentityProvider.objects.create(
        organization=organization,
        alias="exampleu",
        protocol=IDP_PROTOCOL_SAML,
        lifecycle_state=state,
        metadata_source="https://idp.example.edu/metadata.xml",
        metadata_artifact=dict(PARSED_METADATA),
    )


def test_transition_writes_keycloak_and_our_row_together(connection):
    """The lifecycle cannot drift from the realm because one call does both."""

    identity_provider = _identity_provider(OrganizationPageFactory.create())
    connection.identity_providers.get.return_value = IdentityProviderRepresentation(
        alias="exampleu", enabled=False, hide_on_login=True
    )

    transition_identity_provider(
        identity_provider, IDP_STATE_TESTING, connection=connection
    )

    _, payload = connection.identity_providers.update.call_args.args
    assert payload["enabled"] is True
    assert payload["hideOnLogin"] is True

    identity_provider.refresh_from_db()
    assert identity_provider.lifecycle_state == IDP_STATE_TESTING


def test_transition_refuses_to_skip_testing(connection):
    """An IdP goes live only after somebody has logged in through it."""

    identity_provider = _identity_provider(OrganizationPageFactory.create())

    with pytest.raises(InvalidLifecycleTransitionError):
        transition_identity_provider(
            identity_provider, IDP_STATE_ACTIVE, connection=connection
        )

    connection.identity_providers.update.assert_not_called()
    identity_provider.refresh_from_db()
    assert identity_provider.lifecycle_state == IDP_STATE_DRAFT


def test_transition_allows_re_enabling_a_disabled_provider(connection):
    """An IdP that already went through testing can be turned back on."""

    identity_provider = _identity_provider(
        OrganizationPageFactory.create(), state=IDP_STATE_DISABLED
    )
    connection.identity_providers.get.return_value = IdentityProviderRepresentation(
        alias="exampleu", enabled=False, hide_on_login=True
    )

    transition_identity_provider(
        identity_provider, IDP_STATE_ACTIVE, connection=connection
    )

    identity_provider.refresh_from_db()
    assert identity_provider.lifecycle_state == IDP_STATE_ACTIVE


def test_refresh_metadata_leaves_the_artifact_alone_when_the_fetch_fails(
    connection, mocker
):
    """
    An unreachable partner endpoint never clears the stored artifact.

    Storing it is what stops a partner's metadata going away from destroying
    config, so a failed refresh must not undo that.
    """

    identity_provider = _identity_provider(OrganizationPageFactory.create())
    mocker.patch(
        "b2b.provisioning.import_identity_provider_config",
        side_effect=ValueError("unreachable"),
    )

    with pytest.raises(ValueError, match="unreachable"):
        refresh_identity_provider_metadata(identity_provider, connection=connection)

    identity_provider.refresh_from_db()
    assert identity_provider.metadata_artifact == PARSED_METADATA
    connection.identity_providers.update.assert_not_called()


def test_refresh_metadata_stores_what_came_back(connection, mocker):
    """A successful refresh replaces the artifact and stamps when it happened."""

    identity_provider = _identity_provider(OrganizationPageFactory.create())
    refreshed = {"idpEntityId": "https://idp.example.edu/rotated"}
    mocker.patch(
        "b2b.provisioning.import_identity_provider_config", return_value=refreshed
    )
    connection.identity_providers.get.return_value = IdentityProviderRepresentation(
        alias="exampleu", enabled=True, config=dict(PARSED_METADATA)
    )

    refresh_identity_provider_metadata(identity_provider, connection=connection)

    identity_provider.refresh_from_db()
    assert identity_provider.metadata_artifact == refreshed
    assert identity_provider.metadata_fetched_at is not None


def test_delete_identity_provider_unlinks_before_deleting(connection):
    """Unlink from the organization, then remove the instance, then our row."""

    organization = OrganizationPageFactory.create()
    identity_provider = _identity_provider(organization)

    delete_identity_provider(identity_provider, connection=connection)

    connection.organizations.disassociate.assert_called_once_with(
        "identity-providers", organization.sso_organization_id, "exampleu"
    )
    connection.identity_providers.delete.assert_called_once_with("exampleu")
    assert not OrganizationIdentityProvider.objects.filter(alias="exampleu").exists()


def test_delete_identity_provider_refuses_an_unprovisioned_organization(connection):
    """
    Reachable because sso_organization_id is editable in the Wagtail admin.

    Creation requires a provisioned organization, but staff can blank the field
    afterwards. Without the guard the unlink 502s and the IdP can never be
    deleted.
    """

    organization = OrganizationPageFactory.create()
    identity_provider = _identity_provider(organization)
    organization.sso_organization_id = None
    organization.save()
    identity_provider.refresh_from_db()

    with pytest.raises(OrganizationNotProvisionedError):
        delete_identity_provider(identity_provider, connection=connection)

    connection.organizations.disassociate.assert_not_called()
    connection.identity_providers.delete.assert_not_called()
    assert OrganizationIdentityProvider.objects.filter(alias="exampleu").exists()


def test_onboarding_set_state_stamps_the_change():
    """state_changed_at tracks state changes, not every save."""

    organization = OrganizationPageFactory.create()
    onboarding = OrganizationOnboarding.objects.create(organization=organization)
    original = onboarding.state_changed_at

    onboarding.set_state(ONBOARDING_STATE_ORG_CREATED, notes="created by hand")

    onboarding.refresh_from_db()
    assert onboarding.state == ONBOARDING_STATE_ORG_CREATED
    assert onboarding.notes == "created by hand"
    assert onboarding.state_changed_at > original


def test_every_lifecycle_state_has_transitions():
    """
    IDP_ALLOWED_TRANSITIONS covers exactly the lifecycle choices.

    transition_identity_provider indexes the dict by the IdP's current state.
    That is a KeyError waiting to happen only if the two constants drift apart,
    so guard the drift rather than the lookup: a runtime .get() would turn
    "somebody added a fifth state and forgot the transitions" into a silently
    untransitionable IdP, where this fails the build.
    """

    assert set(IDP_ALLOWED_TRANSITIONS) == {state for state, _ in IDP_LIFECYCLE_CHOICES}

    valid_states = set(IDP_ALLOWED_TRANSITIONS)
    for state, destinations in IDP_ALLOWED_TRANSITIONS.items():
        assert set(destinations) <= valid_states, state
        assert state not in destinations, state


def test_create_organization_checks_the_index_page_before_touching_keycloak(
    connection, organization_index
):
    """
    A missing index page fails before the Keycloak write, not after.

    It is a precondition we can check for nothing; checking it after the
    irreversible external write would mean compensating for a failure we could
    have seen coming.
    """

    organization_index.delete()

    with pytest.raises(ImproperlyConfigured):
        create_organization(connection=connection, **_organization_kwargs())

    connection.organizations.create.assert_not_called()
    connection.organizations.delete.assert_not_called()


def _audits(organization):
    return list(
        OrganizationProvisioningAudit.objects.filter(
            organization=organization
        ).order_by("id")
    )


def test_create_organization_is_audited(connection, staff_user):
    """Who created the organization, and with what, is recorded with it."""

    organization = create_organization(
        connection=connection, actor=staff_user, **_organization_kwargs()
    )

    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_ORG_CREATED
    assert audit.acting_user == staff_user
    assert audit.data_before is None
    assert audit.data_after["org_key"] == "EXAMPLEU"
    assert audit.data_after["domains"] == ["example.edu"]
    assert audit.data_after["sso_organization_id"] == str(
        organization.sso_organization_id
    )


def test_an_organization_that_cannot_be_audited_is_not_created(connection, mocker):
    """
    The audit row is in the same transaction as the records it describes.

    An unaudited organization is the thing the audit trail exists to rule out,
    so a failed audit write is compensated like any other failed local write.
    """

    mocker.patch(
        "b2b.provisioning.OrganizationProvisioningAudit.objects.create",
        side_effect=ValueError("no"),
    )

    with pytest.raises(ValueError, match="no"):
        create_organization(connection=connection, **_organization_kwargs())

    connection.organizations.delete.assert_called_once_with(
        connection.organizations.create.return_value
    )
    assert not OrganizationPage.objects.filter(org_key="EXAMPLEU").exists()


def test_update_organization_audits_only_what_changed(connection, staff_user):
    """Fields sent unchanged are not reported as changes."""

    organization = OrganizationPageFactory.create(name="Example University")
    connection.organizations.get.return_value = OrganizationRepresentation(
        id=str(organization.sso_organization_id),
        name=organization.name,
        alias=organization.org_key,
        redirect_url="https://learn.mit.edu/old",
        domains=[OrganizationDomainRepresentation(name="example.edu", verified=True)],
    )

    update_organization(
        organization,
        connection=connection,
        actor=staff_user,
        name="Example University",
        domains=["example.edu", "example.org"],
    )

    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_ORG_UPDATED
    assert audit.acting_user == staff_user
    assert audit.data_before == {"domains": ["example.edu"]}
    assert audit.data_after == {"domains": ["example.edu", "example.org"]}


def test_update_organization_that_changes_nothing_is_not_audited(connection):
    """A no-op PATCH is not a change to review."""

    organization = OrganizationPageFactory.create()
    connection.organizations.get.return_value = OrganizationRepresentation(
        id=str(organization.sso_organization_id),
        name=organization.name,
        alias=organization.org_key,
    )

    update_organization(organization, connection=connection, name=organization.name)

    assert _audits(organization) == []


@pytest.mark.parametrize("has_onboarding", [True, False])
def test_set_onboarding_state_is_audited(staff_user, has_onboarding):
    """
    The before state is recorded, and a missing onboarding record is created.

    Organizations that predate the provisioning API have no onboarding row.
    """

    organization = OrganizationPageFactory.create()
    if has_onboarding:
        OrganizationOnboarding.objects.create(
            organization=organization, state=ONBOARDING_STATE_ORG_CREATED
        )

    onboarding = set_onboarding_state(
        organization, ONBOARDING_STATE_LIVE, notes="went live", actor=staff_user
    )

    assert onboarding.state == ONBOARDING_STATE_LIVE
    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_ONBOARDING_CHANGED
    assert audit.acting_user == staff_user
    assert audit.data_before == (
        {"state": ONBOARDING_STATE_ORG_CREATED, "notes": ""} if has_onboarding else None
    )
    assert audit.data_after == {"state": ONBOARDING_STATE_LIVE, "notes": "went live"}


def test_create_identity_provider_audit_leaves_out_the_client_secret(
    connection, mocked_import_config, staff_user
):
    """The secret goes to Keycloak and nowhere else, the audit trail included."""

    organization = OrganizationPageFactory.create()
    secret = FAKE.password()

    create_identity_provider(
        organization,
        connection=connection,
        actor=staff_user,
        alias="exampleu-oidc",
        protocol=IDP_PROTOCOL_OIDC,
        metadata_url="https://idp.example.edu/.well-known/openid-configuration",
        client_id="mitxonline",
        client_secret=secret,
    )

    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_IDP_CREATED
    assert audit.identity_provider_alias == "exampleu-oidc"
    assert audit.data_after["client_id"] == "mitxonline"
    assert audit.data_after["lifecycle_state"] == IDP_STATE_DRAFT
    assert secret not in str(audit.data_after)
    assert audit.data_before is None


def test_transition_is_audited(connection, staff_user):
    """Going live is the change most worth being able to attribute."""

    organization = OrganizationPageFactory.create()
    identity_provider = _identity_provider(organization, state=IDP_STATE_TESTING)
    connection.identity_providers.get.return_value = IdentityProviderRepresentation(
        alias="exampleu", enabled=True, hide_on_login=True
    )

    transition_identity_provider(
        identity_provider, IDP_STATE_ACTIVE, connection=connection, actor=staff_user
    )

    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_IDP_TRANSITIONED
    assert audit.acting_user == staff_user
    assert audit.identity_provider_alias == "exampleu"
    assert audit.data_before == {"lifecycle_state": IDP_STATE_TESTING}
    assert audit.data_after == {"lifecycle_state": IDP_STATE_ACTIVE}


def test_a_refused_transition_is_not_audited(connection):
    """Nothing changed, so there is nothing to record."""

    organization = OrganizationPageFactory.create()
    identity_provider = _identity_provider(organization)

    with pytest.raises(InvalidLifecycleTransitionError):
        transition_identity_provider(
            identity_provider, IDP_STATE_ACTIVE, connection=connection
        )

    assert _audits(organization) == []


def test_refresh_metadata_audits_the_changed_keys(connection, mocker, staff_user):
    """A rotated certificate shows up as exactly that, not as the whole config."""

    organization = OrganizationPageFactory.create()
    identity_provider = _identity_provider(organization)
    refreshed = {**PARSED_METADATA, "idpEntityId": "https://idp.example.edu/rotated"}
    mocker.patch(
        "b2b.provisioning.import_identity_provider_config", return_value=refreshed
    )
    connection.identity_providers.get.return_value = IdentityProviderRepresentation(
        alias="exampleu", enabled=True, config=dict(PARSED_METADATA)
    )

    refresh_identity_provider_metadata(
        identity_provider, connection=connection, actor=staff_user
    )

    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_IDP_METADATA_REFRESHED
    assert audit.data_before == {"idpEntityId": PARSED_METADATA["idpEntityId"]}
    assert audit.data_after == {"idpEntityId": "https://idp.example.edu/rotated"}


def test_delete_identity_provider_audit_outlives_the_provider(connection, staff_user):
    """The alias is a string, so the record survives the row it describes."""

    organization = OrganizationPageFactory.create()
    identity_provider = _identity_provider(organization, state=IDP_STATE_DISABLED)

    delete_identity_provider(identity_provider, connection=connection, actor=staff_user)

    (audit,) = _audits(organization)
    assert audit.action == PROVISIONING_ACTION_IDP_DELETED
    assert audit.identity_provider_alias == "exampleu"
    assert audit.data_before["lifecycle_state"] == IDP_STATE_DISABLED
    assert not OrganizationIdentityProvider.objects.filter(alias="exampleu").exists()


def test_audit_records_cannot_be_rewritten(staff_user):
    """Append-only: saving an existing record is refused."""

    organization = OrganizationPageFactory.create()
    set_onboarding_state(organization, ONBOARDING_STATE_LIVE, actor=staff_user)
    (audit,) = _audits(organization)

    audit.data_after = {"state": "something else"}
    with pytest.raises(ValueError, match="cannot be changed"):
        audit.save()


def test_an_actor_with_audit_history_cannot_be_deleted(staff_user):
    """Deleting the account would lose who made the change, so it is refused."""

    organization = OrganizationPageFactory.create()
    set_onboarding_state(organization, ONBOARDING_STATE_LIVE, actor=staff_user)

    with pytest.raises(ProtectedError):
        staff_user.delete()

    (audit,) = _audits(organization)
    assert audit.acting_user == staff_user


def test_audit_records_the_org_key(staff_user):
    """Every row carries the org_key, so history can be found without the page."""

    organization = OrganizationPageFactory.create()
    set_onboarding_state(organization, ONBOARDING_STATE_LIVE, actor=staff_user)

    (audit,) = _audits(organization)
    assert audit.org_key == organization.org_key


def test_audit_survives_the_organization_being_deleted(staff_user):
    """Deleting the page in Wagtail must not take its provisioning history with it."""

    organization = OrganizationPageFactory.create()
    org_key = organization.org_key
    set_onboarding_state(organization, ONBOARDING_STATE_LIVE, actor=staff_user)

    organization.delete()

    (audit,) = OrganizationProvisioningAudit.objects.filter(org_key=org_key)
    assert audit.organization is None
    assert audit.acting_user == staff_user
