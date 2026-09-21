"""
Staff-only provisioning of per-customer Keycloak resources (capability C1).

The ownership split this implements: Pulumi keeps the realm, its authentication
flows, client scopes, clients and service-account grants; this module owns
Keycloak organizations, their domains, identity providers, IdP attribute
mappers and org<->IdP links, alongside the MITx Online records that go with
them.

Pulumi only deletes resources that are in its own state, so an organization
created here is invisible to it and safe. The cross-system hazard is alias
collision, not deletion: organization and IdP aliases are realm-wide, so an
alias created here will break a later pulumi up that declares the same name.
Every create in this module checks the realm before writing.

See docs/source/b2b/provisioning_api.md.
"""

import logging

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from mitol.common.utils import now_in_utc

from b2b.constants import (
    IDP_ALLOWED_TRANSITIONS,
    IDP_PROTOCOL_OIDC,
    IDP_PROTOCOL_SAML,
    IDP_STATE_DRAFT,
    IDP_STATE_KEYCLOAK_FLAGS,
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
from b2b.keycloak_admin_api import (
    KCAM_IDENTITY_PROVIDERS,
    KCAM_ORGANIZATIONS,
    bootstrap_client,
    get_keycloak_model,
    import_identity_provider_config,
)
from b2b.keycloak_admin_dataclasses import IdentityProviderMapperRepresentation
from b2b.models import (
    OrganizationIdentityProvider,
    OrganizationIndexPage,
    OrganizationOnboarding,
    OrganizationPage,
    OrganizationProvisioningAudit,
)

log = logging.getLogger(__name__)

ORG_IDP_ASSOCIATION = "identity-providers"

# Keycloak's attribute-importer mapper, per protocol, and the config key each
# one reads the source attribute from. These are the same mappers
# ol-infrastructure's AttributeImporterIdentityProviderMapper resources produce,
# so an IdP built here is shaped like the ones Pulumi still declares.
IDP_ATTRIBUTE_MAPPERS = {
    IDP_PROTOCOL_SAML: "saml-user-attribute-idp-mapper",
    IDP_PROTOCOL_OIDC: "oidc-user-attribute-idp-mapper",
}


def _audit(  # noqa: PLR0913
    organization,
    action,
    *,
    actor,
    identity_provider_alias="",
    data_before=None,
    data_after=None,
):
    """
    Record a provisioning change.

    Called by every function below that changes something, after the change
    has happened, so the audit trail covers any caller and not only the API.
    """

    OrganizationProvisioningAudit.objects.create(
        organization=organization,
        org_key=organization.org_key,
        action=action,
        acting_user=actor,
        identity_provider_alias=identity_provider_alias,
        data_before=data_before,
        data_after=data_after,
    )


def _onboarding_snapshot(onboarding):
    """Return the audited fields of an onboarding record."""

    if onboarding is None:
        return None
    return {"state": onboarding.state, "notes": onboarding.notes}


class KeycloakConnection:
    """
    A Keycloak admin client and the models built on it.

    Bootstrapping the client fetches OIDC discovery and a token, so the
    provisioning calls share one rather than each making their own.
    """

    def __init__(self, client=None):
        self.client = client or bootstrap_client()
        self.organizations = get_keycloak_model(*KCAM_ORGANIZATIONS, client=self.client)
        self.identity_providers = get_keycloak_model(
            *KCAM_IDENTITY_PROVIDERS, client=self.client
        )


def realm_organization_aliases(connection):
    """
    Return every organization alias in the realm, lowercased.

    Includes the organizations Pulumi still owns - that is the point.

    Args:
    - connection (KeycloakConnection): the Keycloak connection to use.
    Returns:
    - set[str]: the aliases in use.
    """

    return {
        org.alias.lower()
        for org in connection.organizations.list_all()
        if org.alias is not None
    }


def realm_identity_provider_aliases(connection):
    """
    Return every identity provider alias in the realm, lowercased.

    Args:
    - connection (KeycloakConnection): the Keycloak connection to use.
    Returns:
    - set[str]: the aliases in use.
    """

    return {
        idp.alias.lower()
        for idp in connection.identity_providers.list_all()
        if idp.alias is not None
    }


def _require_provisioned(organization):
    """
    Refuse to act on an organization that has no Keycloak counterpart.

    Without this the admin call goes to organizations/None, Keycloak answers
    404, and the operator is told the Keycloak API failed - a 502 they would
    retry forever. Keycloak is fine; our record is the incomplete one.

    Args:
    - organization (OrganizationPage): the organization to check.
    Raises:
    - OrganizationNotProvisionedError: it has no sso_organization_id.
    """

    if not organization.sso_organization_id:
        msg = (
            f"Organization '{organization.org_key}' has no Keycloak "
            "organization. It predates this API and needs backfilling before "
            "it can be managed here."
        )
        raise OrganizationNotProvisionedError(msg)


def _find_organization_by_alias(connection, alias):
    """Return the realm's organization with this alias, or None."""

    return next(
        (
            org
            for org in connection.organizations.list_all()
            if org.alias is not None and org.alias.lower() == alias.lower()
        ),
        None,
    )


def create_organization(  # noqa: PLR0913
    *,
    name,
    org_key,
    org_key_prefix=None,
    domains=(),
    description="",
    redirect_url="",
    connection=None,
    actor=None,
):
    """
    Create a Keycloak organization and the MITx Online records beside it.

    The ordering is what makes this safe. Keycloak has no transactions, so the
    Keycloak write goes first - it is the step most likely to fail for reasons
    outside our control - and the MITx Online writes go into one atomic block
    afterwards. A failure there is compensated by deleting the Keycloak
    organization we just made, because a Keycloak org with no MITx Online
    counterpart is exactly the orphan shape this exists to prevent.

    The Keycloak alias is the org_key verbatim. That is not cosmetic:
    reconcile_single_keycloak_org derives org_key from the alias when it adopts
    an organization, so any other choice would give an adopted org a different
    org_key from the one it was created with - and org_key is baked into every
    B2B courseware ID.

    Args:
    - name (str): the organization's display name
    - org_key (str): the immutable short key, used as the Keycloak alias
    - org_key_prefix (str): courseware ID prefix; defaults to the model default
    - domains (list[str]): email domains to assert for the organization
    - description (str): free-form description
    - redirect_url (str): where Keycloak sends members after login
    - connection (KeycloakConnection): an existing connection, if any
    - actor (User): who asked for this, for the audit trail
    Returns:
    - OrganizationPage: the new organization
    Raises:
    - AliasCollisionError: org_key is taken here or in the realm
    - OrganizationNameCollisionError: the name's page slug is already taken
    - OrphanedKeycloakOrganizationError: the MITx Online write and its
      compensating delete both failed
    - requests.HTTPError: Keycloak rejected the create
    """

    connection = connection or KeycloakConnection()

    if OrganizationPage.objects.filter(org_key=org_key).exists():
        msg = f"An organization with org key '{org_key}' already exists."
        raise AliasCollisionError(msg)

    if org_key.lower() in realm_organization_aliases(connection):
        msg = (
            f"The alias '{org_key}' is already in use by an organization in the "
            "Keycloak realm."
        )
        raise AliasCollisionError(msg)

    # Resolve the parent page here rather than inside the transaction below. It
    # is a precondition we can check before touching Keycloak, and a
    # precondition checked after the irreversible external write is one the
    # compensation has to clean up for no reason.
    organization_index = OrganizationIndexPage.objects.first()
    if organization_index is None:
        msg = (
            "No OrganizationIndexPage exists; the CMS is not set up to hold "
            "organizations."
        )
        raise ImproperlyConfigured(msg)

    # add_child() enforces sibling slug uniqueness with a ValidationError, after
    # the Keycloak write. Checking here keeps a duplicate name from creating and
    # then compensating a Keycloak organization, and gives the caller a 409.
    if (
        organization_index.get_children()
        .filter(slug=OrganizationPage.slug_for_name(name))
        .exists()
    ):
        msg = (
            f"An organization named '{name}', or one whose name produces the same "
            "page slug, already exists."
        )
        raise OrganizationNameCollisionError(msg)

    # Domains are written verified, with no verification having occurred: staff
    # are asserting them. That is defensible only while the asserting party is
    # MIT staff, and stops being so the moment the partner-facing wizard (C2)
    # lets a customer assert their own domain.
    keycloak_payload = {
        "name": name,
        "alias": org_key,
        "enabled": True,
        "description": description,
        "redirectUrl": redirect_url,
        "domains": [{"name": domain, "verified": True} for domain in domains],
    }

    sso_organization_id = connection.organizations.create(keycloak_payload)

    if not sso_organization_id:
        # Keycloak answers the create with 201 and an empty body, so the ID
        # normally comes from the Location header. Fall back to looking the
        # organization up by the alias we just claimed.
        created = _find_organization_by_alias(connection, org_key)
        sso_organization_id = created.id if created else None

    if not sso_organization_id:
        # Keycloak accepted the create but we cannot find what it made. Writing
        # our row anyway would produce an OrganizationPage with a null
        # sso_organization_id, which is the silently-broken shape this saga
        # exists to prevent - attach_user() would no-op for every member. We
        # cannot compensate either, because the delete needs the ID we do not
        # have. Leave it for reconcile_keycloak_orgs to adopt by alias.
        log.error(
            "Created a Keycloak organization with alias %s but could not "
            "resolve its ID, from the Location header or by lookup",
            org_key,
        )
        msg = (
            f"Keycloak accepted the organization '{org_key}' but did not "
            "report its ID, so no MITx Online record could be written."
        )
        raise OrphanedKeycloakOrganizationError(msg)

    try:
        with transaction.atomic():
            organization = OrganizationPage(
                name=name,
                org_key=org_key,
                description=description,
                sso_organization_id=sso_organization_id,
            )
            if org_key_prefix:
                organization.org_key_prefix = org_key_prefix

            organization_index.add_child(instance=organization)
            organization.save()

            OrganizationOnboarding.objects.create(
                organization=organization,
                state=ONBOARDING_STATE_ORG_CREATED,
                state_changed_at=now_in_utc(),
            )

            _audit(
                organization,
                PROVISIONING_ACTION_ORG_CREATED,
                actor=actor,
                data_after={
                    "name": name,
                    "org_key": org_key,
                    "org_key_prefix": organization.org_key_prefix,
                    "description": description,
                    "redirect_url": redirect_url,
                    "domains": list(domains),
                    "sso_organization_id": str(sso_organization_id),
                },
            )
    except Exception as write_error:
        try:
            connection.organizations.delete(sso_organization_id)
        except Exception as compensation_error:
            # Both writes failed. Do not retry against a system that just
            # failed - log the orphan loudly and let reconcile_keycloak_orgs
            # adopt it on its next run, which is the correct outcome anyway.
            log.error(  # noqa: TRY400
                "Orphaned Keycloak organization %s (alias %s): the MITx Online "
                "write failed and the compensating delete failed too",
                sso_organization_id,
                org_key,
            )
            msg = (
                f"Keycloak organization {sso_organization_id} was created but "
                "MITx Online records could not be written and the organization "
                "could not be removed."
            )
            raise OrphanedKeycloakOrganizationError(msg) from compensation_error
        raise write_error  # noqa: TRY201

    return organization


def update_organization(  # noqa: PLR0913
    organization,
    *,
    name=None,
    description=None,
    redirect_url=None,
    domains=None,
    connection=None,
    actor=None,
):
    """
    Update an organization in both systems.

    org_key is deliberately not updatable: it is in every B2B courseware ID via
    create_contract_run_key, which is also why reconcile_single_keycloak_org
    refuses to change it on adoption.

    Keycloak's organization PUT replaces rather than merges, so this reads the
    current representation and writes it back with the changes applied.

    Args:
    - organization (OrganizationPage): the organization to update
    - name (str): new display name, if changing
    - description (str): new description, if changing
    - redirect_url (str): new post-login redirect, if changing
    - domains (list[str]): the complete new domain list, if changing
    - connection (KeycloakConnection): an existing connection, if any
    - actor (User): who asked for this, for the audit trail
    Returns:
    - OrganizationPage: the updated organization
    Raises:
    - OrganizationNotProvisionedError: the organization has no Keycloak record
    """

    _require_provisioned(organization)

    connection = connection or KeycloakConnection()

    keycloak_org = connection.organizations.get(organization.sso_organization_id)
    payload = keycloak_org.model_dump(by_alias=True, exclude_none=True)

    current = {
        "name": organization.name,
        "description": organization.description,
        "redirect_url": keycloak_org.redirect_url,
        "domains": [domain.name for domain in keycloak_org.domains or []],
    }
    requested = {
        "name": name,
        "description": description,
        "redirect_url": redirect_url,
        "domains": list(domains) if domains is not None else None,
    }
    changed = {
        field: value
        for field, value in requested.items()
        if value is not None and value != current[field]
    }

    if name is not None:
        payload["name"] = name
        organization.name = name
    if description is not None:
        payload["description"] = description
        organization.description = description
    if redirect_url is not None:
        payload["redirectUrl"] = redirect_url
    if domains is not None:
        payload["domains"] = [{"name": domain, "verified": True} for domain in domains]

    connection.organizations.update(organization.sso_organization_id, payload)

    with transaction.atomic():
        organization.save()
        if changed:
            _audit(
                organization,
                PROVISIONING_ACTION_ORG_UPDATED,
                actor=actor,
                data_before={field: current[field] for field in changed},
                data_after=changed,
            )

    return organization


def set_onboarding_state(organization, state, *, notes=None, actor=None):
    """
    Record where an organization is in the onboarding sequence.

    Descriptive only: nothing gates on the state.

    Args:
    - organization (OrganizationPage): the organization
    - state (str): the onboarding state to record
    - notes (str): replacement notes, if any
    - actor (User): who recorded it, for the audit trail
    Returns:
    - OrganizationOnboarding: the updated record
    """

    with transaction.atomic():
        onboarding = OrganizationOnboarding.objects.filter(
            organization=organization
        ).first()
        before = _onboarding_snapshot(onboarding)
        onboarding = onboarding or OrganizationOnboarding(organization=organization)
        onboarding.set_state(state, notes=notes)

        _audit(
            organization,
            PROVISIONING_ACTION_ONBOARDING_CHANGED,
            actor=actor,
            data_before=before,
            data_after=_onboarding_snapshot(onboarding),
        )

    return onboarding


def parse_identity_provider_metadata(
    protocol, *, metadata_url=None, metadata_xml=None, connection=None
):
    """
    Parse IdP metadata without creating anything.

    Keycloak does the parsing. This is the cheapest useful call in the API and
    the one the eventual wizard leans on hardest: paste a metadata URL, see what
    Keycloak makes of it, before committing to a resource.

    It is also the endpoint most likely to be abused as an SSRF probe, since the
    URL form makes Keycloak fetch a caller-supplied address and that egress is
    confirmed working. Keep it staff-only.

    Args:
    - protocol (str): "saml" or "oidc"
    - metadata_url (str): a metadata or discovery URL for Keycloak to fetch
    - metadata_xml (str): the metadata document, uploaded instead of fetched
    - connection (KeycloakConnection): an existing connection, if any
    Returns:
    - dict: the config map Keycloak parsed out of the metadata
    """

    connection = connection or KeycloakConnection()

    return import_identity_provider_config(
        protocol,
        from_url=metadata_url,
        metadata=metadata_xml,
        client=connection.client,
    )


def _attribute_mapper_payload(protocol, alias, user_attribute, source, *, friendly):
    """Build one attribute-importer mapper representation."""

    if protocol == IDP_PROTOCOL_SAML:
        source_key = "attribute.friendly.name" if friendly else "attribute.name"
        config = {
            source_key: source,
            "user.attribute": user_attribute,
            "syncMode": "INHERIT",
            "attribute.name.format": "ATTRIBUTE_FORMAT_URI",
        }
    else:
        config = {
            "claim": source,
            "user.attribute": user_attribute,
            "syncMode": "INHERIT",
        }

    return {
        "name": f"{alias}-{user_attribute}-mapper",
        "identityProviderAlias": alias,
        "identityProviderMapper": IDP_ATTRIBUTE_MAPPERS[protocol],
        "config": config,
    }


def _create_attribute_mappers(
    connection, alias, protocol, attribute_map, attribute_name_map
):
    """Create the IdP's attribute-importer mappers in Keycloak."""

    for user_attribute, source in (attribute_map or {}).items():
        connection.client.create_returning_id(
            f"identity-provider/instances/{alias}/mappers",
            _attribute_mapper_payload(
                protocol, alias, user_attribute, source, friendly=True
            ),
        )

    for user_attribute, source in (attribute_name_map or {}).items():
        connection.client.create_returning_id(
            f"identity-provider/instances/{alias}/mappers",
            _attribute_mapper_payload(
                protocol, alias, user_attribute, source, friendly=False
            ),
        )


def _replace_attribute_mappers(
    connection, alias, protocol, attribute_map, attribute_name_map
):
    """
    Replace the IdP's attribute-importer mappers with the supplied set.

    The two maps together are the whole mapper set, the way `domains` is the
    whole domain list on an organization update: what is on the IdP now goes,
    and what is supplied takes its place. A merge would have to guess which
    mapper an operator meant to change - Keycloak keys them by a generated id,
    and the only name we give them is `{alias}-{attribute}-mapper`.

    Only the attribute importers are replaced. A mapper of another type - a
    username template, a hardcoded role - was added out of band and has nothing
    to do with the maps being supplied, so an attribute edit does not destroy
    it.

    Args:
    - connection (KeycloakConnection): the Keycloak connection to use
    - alias (str): the IdP alias
    - protocol (str): "saml" or "oidc"
    - attribute_map (dict): user attribute -> SAML friendly name / OIDC claim
    - attribute_name_map (dict): user attribute -> SAML attribute name
    """

    endpoint = f"identity-provider/instances/{alias}/mappers"
    existing = connection.client.list(endpoint, IdentityProviderMapperRepresentation)

    for mapper in existing:
        if mapper.identity_provider_mapper in IDP_ATTRIBUTE_MAPPERS.values():
            connection.client.delete(f"{endpoint}/{mapper.id}")

    _create_attribute_mappers(
        connection, alias, protocol, attribute_map, attribute_name_map
    )


def create_identity_provider(  # noqa: PLR0913
    organization,
    *,
    alias,
    protocol,
    display_name="",
    metadata_url=None,
    metadata_xml=None,
    client_id=None,
    client_secret=None,
    attribute_map=None,
    attribute_name_map=None,
    connection=None,
    actor=None,
):
    """
    Create an identity provider for an organization and link the two.

    The IdP starts in `draft`, which is disabled in Keycloak. Nobody can reach
    it until somebody transitions it to `testing`.

    Same ordering rule as the organization saga: Keycloak first, our row last,
    compensating delete if our row cannot be written.

    Args:
    - organization (OrganizationPage): the organization to attach the IdP to
    - alias (str): the realm-wide IdP alias
    - protocol (str): "saml" or "oidc"
    - display_name (str): the IdP's display name
    - metadata_url (str): SAML metadata or OIDC discovery URL
    - metadata_xml (str): SAML metadata document, instead of a URL
    - client_id (str): OIDC client ID
    - client_secret (str): OIDC client secret
    - attribute_map (dict): user attribute -> SAML friendly name / OIDC claim
    - attribute_name_map (dict): user attribute -> SAML attribute name
    - connection (KeycloakConnection): an existing connection, if any
    - actor (User): who asked for this, for the audit trail
    Returns:
    - OrganizationIdentityProvider: the new record
    Raises:
    - AliasCollisionError: the alias is taken here or in the realm
    - OrganizationNotProvisionedError: the organization has no Keycloak record
    """

    # Before anything is written. Without it the IdP is created in Keycloak and
    # only the org<->IdP link fails, so the compensation deletes an IdP we
    # should never have made - a wasted round trip reported as 502.
    _require_provisioned(organization)

    connection = connection or KeycloakConnection()

    if OrganizationIdentityProvider.objects.filter(alias=alias).exists():
        msg = f"An identity provider with alias '{alias}' already exists."
        raise AliasCollisionError(msg)

    if alias.lower() in realm_identity_provider_aliases(connection):
        msg = (
            f"The alias '{alias}' is already in use by an identity provider in "
            "the Keycloak realm."
        )
        raise AliasCollisionError(msg)

    # The artifact is what Keycloak parsed out of the partner's metadata, and
    # nothing else: the OIDC client secret we add below goes to Keycloak but is
    # never persisted here, because this field is served back over the API.
    metadata_artifact = parse_identity_provider_metadata(
        protocol,
        metadata_url=metadata_url,
        metadata_xml=metadata_xml,
        connection=connection,
    )
    fetched_at = now_in_utc()

    config = dict(metadata_artifact)
    if protocol == IDP_PROTOCOL_OIDC:
        config.update({"clientId": client_id, "clientSecret": client_secret})
    elif metadata_url:
        # Let Keycloak re-read the descriptor itself, matching what the Pulumi
        # SAML resources set.
        config.update(
            {
                "metadataDescriptorUrl": metadata_url,
                "useMetadataDescriptorUrl": "true",
            }
        )

    draft_flags = IDP_STATE_KEYCLOAK_FLAGS[IDP_STATE_DRAFT]
    internal_id = connection.identity_providers.create(
        {
            "alias": alias,
            "displayName": display_name,
            "providerId": protocol,
            "enabled": draft_flags["enabled"],
            "hideOnLogin": draft_flags["hideOnLogin"],
            "config": config,
        }
    )

    try:
        _create_attribute_mappers(
            connection, alias, protocol, attribute_map, attribute_name_map
        )
        connection.organizations.associate(
            ORG_IDP_ASSOCIATION, organization.sso_organization_id, alias
        )
        with transaction.atomic():
            identity_provider = OrganizationIdentityProvider.objects.create(
                organization=organization,
                alias=alias,
                protocol=protocol,
                display_name=display_name,
                internal_id=internal_id or "",
                metadata_source=metadata_url or metadata_xml or "",
                metadata_artifact=metadata_artifact,
                metadata_fetched_at=fetched_at,
            )
            # The client secret is left out on purpose: it went to Keycloak
            # and is not stored anywhere on our side, this included.
            _audit(
                organization,
                PROVISIONING_ACTION_IDP_CREATED,
                actor=actor,
                identity_provider_alias=alias,
                data_after={
                    "protocol": protocol,
                    "display_name": display_name,
                    "lifecycle_state": identity_provider.lifecycle_state,
                    "metadata_url": metadata_url or None,
                    "metadata_xml_uploaded": bool(metadata_xml),
                    "client_id": client_id or None,
                    "attribute_map": attribute_map or {},
                    "attribute_name_map": attribute_name_map or {},
                },
            )
    except Exception:
        connection.identity_providers.delete(alias)
        raise

    return identity_provider


def update_identity_provider(  # noqa: PLR0913
    identity_provider,
    *,
    display_name=None,
    metadata_url=None,
    metadata_xml=None,
    client_id=None,
    client_secret=None,
    attribute_map=None,
    attribute_name_map=None,
    connection=None,
):
    """
    Update an identity provider in place.

    The alternative is delete and recreate, and Keycloak's IdP delete runs
    `preRemove` on the provider, which deletes every user's federated identity
    link to it. Those users then have to go back through first-broker-login.
    Rotating a client secret or fixing one mapper must not cost that, which is
    why this exists.

    Keycloak's IdP PUT replaces rather than merges, so this reads the current
    representation and writes it back with the changes applied - including the
    lifecycle flags, which keeps the transition machinery the only thing that
    moves them. A client secret that is not being changed comes back from
    Keycloak masked and is written back masked; Keycloak restores the stored
    value when it sees the sentinel (IdentityProviderResource.updateIdpFromRep,
    Keycloak main). The alias cannot change here and Keycloak rejects it too.

    There is no compensation. The IdP write, the mapper replacement and our
    save happen in that order, and a failure part way through leaves Keycloak
    ahead of our row - on a SAML IdP, possibly with fewer mappers than it
    started with. Every step is idempotent for the same request body, so the
    recovery is to send the same PATCH again; unlike a create, there is nothing
    half-made to delete.

    Args:
    - identity_provider (OrganizationIdentityProvider): the IdP to update
    - display_name (str): new display name, if changing
    - metadata_url (str): new metadata or OIDC discovery URL, if changing
    - metadata_xml (str): new SAML metadata document, if changing
    - client_id (str): new OIDC client ID, if changing
    - client_secret (str): new OIDC client secret, if rotating
    - attribute_map (dict): user attribute -> SAML friendly name / OIDC claim
    - attribute_name_map (dict): user attribute -> SAML attribute name
    - connection (KeycloakConnection): an existing connection, if any
    Returns:
    - OrganizationIdentityProvider: the updated record
    """

    connection = connection or KeycloakConnection()

    metadata_source = metadata_url or metadata_xml
    metadata_artifact = None

    if metadata_source:
        metadata_artifact = parse_identity_provider_metadata(
            identity_provider.protocol,
            metadata_url=metadata_url,
            metadata_xml=metadata_xml,
            connection=connection,
        )

    keycloak_idp = connection.identity_providers.get(identity_provider.alias)
    payload = keycloak_idp.model_dump(by_alias=True, exclude_none=True)
    config = dict(payload.get("config") or {})

    if metadata_artifact is not None:
        config.update(metadata_artifact)
        if identity_provider.protocol == IDP_PROTOCOL_SAML:
            # Whichever source is not in use has to be turned off explicitly.
            # An IdP created from a URL keeps re-reading that URL otherwise,
            # so an operator who replaces it with uploaded XML gets a 200 and
            # a realm still following the descriptor they just replaced.
            config.update(
                {
                    "metadataDescriptorUrl": metadata_url or "",
                    "useMetadataDescriptorUrl": "true" if metadata_url else "false",
                }
            )
    if client_id is not None:
        config["clientId"] = client_id
    if client_secret is not None:
        config["clientSecret"] = client_secret
    if display_name is not None:
        payload["displayName"] = display_name

    payload["config"] = config
    connection.identity_providers.update(identity_provider.alias, payload)

    if attribute_map is not None or attribute_name_map is not None:
        _replace_attribute_mappers(
            connection,
            identity_provider.alias,
            identity_provider.protocol,
            attribute_map,
            attribute_name_map,
        )

    if display_name is not None:
        identity_provider.display_name = display_name
    if metadata_artifact is not None:
        # The artifact stays what Keycloak parsed and nothing else: this field
        # is served back over the API, and an OIDC update carries a secret.
        identity_provider.metadata_source = metadata_source
        identity_provider.metadata_artifact = metadata_artifact
        identity_provider.metadata_fetched_at = now_in_utc()
    identity_provider.save()

    return identity_provider


def refresh_identity_provider_metadata(
    identity_provider, *, connection=None, actor=None
):
    """
    Re-fetch the IdP's metadata and store what came back.

    An explicit operation, never a side effect of an unrelated change. On
    failure the stored artifact is left exactly as it was - that is the whole
    reason it is stored.

    Args:
    - identity_provider (OrganizationIdentityProvider): the IdP to refresh
    - connection (KeycloakConnection): an existing connection, if any
    - actor (User): who asked for this, for the audit trail
    Returns:
    - OrganizationIdentityProvider: the refreshed record
    """

    connection = connection or KeycloakConnection()
    source = identity_provider.metadata_source

    config = parse_identity_provider_metadata(
        identity_provider.protocol,
        metadata_url=source if not source.lstrip().startswith("<") else None,
        metadata_xml=source if source.lstrip().startswith("<") else None,
        connection=connection,
    )

    keycloak_idp = connection.identity_providers.get(identity_provider.alias)
    payload = keycloak_idp.model_dump(by_alias=True, exclude_none=True)
    payload["config"] = {**(payload.get("config") or {}), **config}
    connection.identity_providers.update(identity_provider.alias, payload)

    before = identity_provider.metadata_artifact or {}
    changed_keys = sorted(
        key
        for key in before.keys() | config.keys()
        if before.get(key) != config.get(key)
    )

    identity_provider.metadata_artifact = config
    identity_provider.metadata_fetched_at = now_in_utc()

    with transaction.atomic():
        identity_provider.save()
        # Only the keys that changed. A refresh that finds nothing new is still
        # recorded, as an empty diff, because "somebody checked" is worth
        # knowing when a partner rotates a certificate.
        _audit(
            identity_provider.organization,
            PROVISIONING_ACTION_IDP_METADATA_REFRESHED,
            actor=actor,
            identity_provider_alias=identity_provider.alias,
            data_before={key: before.get(key) for key in changed_keys},
            data_after={key: config.get(key) for key in changed_keys},
        )

    return identity_provider


def transition_identity_provider(
    identity_provider, state, *, connection=None, actor=None
):
    """
    Move an identity provider to a new lifecycle state.

    The only thing that moves the lifecycle, and it writes Keycloak's own
    enabled/hideOnLogin in the same operation so our record and the realm cannot
    drift. Keycloak goes first: our row lagging the realm is recoverable, a
    partner integration disabled without our knowing is not.

    Args:
    - identity_provider (OrganizationIdentityProvider): the IdP to move
    - state (str): the lifecycle state to move to
    - connection (KeycloakConnection): an existing connection, if any
    - actor (User): who asked for this, for the audit trail
    Returns:
    - OrganizationIdentityProvider: the updated record
    Raises:
    - InvalidLifecycleTransitionError: the transition is not allowed
    """

    current = identity_provider.lifecycle_state

    if state not in IDP_ALLOWED_TRANSITIONS[current]:
        msg = (
            f"Cannot move identity provider '{identity_provider.alias}' from "
            f"'{current}' to '{state}'."
        )
        raise InvalidLifecycleTransitionError(msg)

    connection = connection or KeycloakConnection()
    flags = IDP_STATE_KEYCLOAK_FLAGS[state]

    keycloak_idp = connection.identity_providers.get(identity_provider.alias)
    payload = keycloak_idp.model_dump(by_alias=True, exclude_none=True)
    payload.update(flags)
    connection.identity_providers.update(identity_provider.alias, payload)

    identity_provider.lifecycle_state = state

    with transaction.atomic():
        identity_provider.save()
        _audit(
            identity_provider.organization,
            PROVISIONING_ACTION_IDP_TRANSITIONED,
            actor=actor,
            identity_provider_alias=identity_provider.alias,
            data_before={"lifecycle_state": current},
            data_after={"lifecycle_state": state},
        )

    return identity_provider


def delete_identity_provider(identity_provider, *, connection=None, actor=None):
    """
    Unlink and delete an identity provider.

    Args:
    - identity_provider (OrganizationIdentityProvider): the IdP to delete
    - connection (KeycloakConnection): an existing connection, if any
    - actor (User): who asked for this, for the audit trail
    Raises:
    - OrganizationNotProvisionedError: the organization has no Keycloak record
    """

    # Creation requires a provisioned organization, so this looks unreachable -
    # but sso_organization_id is an editable panel on OrganizationPage
    # (content_panels) and is nullable, so staff can blank it in the Wagtail
    # admin after the IdP exists. Without the guard the unlink 502s and the IdP
    # can never be deleted, with a message blaming Keycloak.
    _require_provisioned(identity_provider.organization)

    connection = connection or KeycloakConnection()

    connection.organizations.disassociate(
        ORG_IDP_ASSOCIATION,
        identity_provider.organization.sso_organization_id,
        identity_provider.alias,
    )
    connection.identity_providers.delete(identity_provider.alias)

    with transaction.atomic():
        _audit(
            identity_provider.organization,
            PROVISIONING_ACTION_IDP_DELETED,
            actor=actor,
            identity_provider_alias=identity_provider.alias,
            data_before={
                "protocol": identity_provider.protocol,
                "display_name": identity_provider.display_name,
                "lifecycle_state": identity_provider.lifecycle_state,
                "metadata_source": identity_provider.metadata_source,
            },
        )
        identity_provider.delete()
