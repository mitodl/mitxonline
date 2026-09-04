"""Exceptions for the B2B app."""


class SourceCourseIncompleteError(Exception):
    """
    Raised if the source course being added to a contract is incomplete.

    Specifically, this is raised if the source course passed to create_contract_run
    doesn't have any course runs. We need at least one to clone.
    """


class TargetCourseRunExistsError(Exception):
    """Raised if the target course run we're trying to create already exists."""


class KeycloakAdminImproperlyConfiguredError(Exception):
    """Raised if Keycloak admin client is improperly configured."""


class AliasCollisionError(Exception):
    """
    Raised when a Keycloak alias is already taken.

    Organization and identity provider aliases are realm-wide, and the realm is
    shared with the resources Pulumi still declares, so an alias that is free in
    our own tables can still collide. Creating one anyway would break the next
    pulumi up that declares the same name.
    """


class InvalidLifecycleTransitionError(Exception):
    """Raised when an identity provider is asked to skip a lifecycle state."""


class OrphanedKeycloakOrganizationError(Exception):
    """
    Raised when a Keycloak organization is left behind by a failed create.

    The organization creation saga compensates for a failed MITx Online write by
    deleting the Keycloak organization it just made. When that compensating
    delete also fails, the organization is orphaned and this is raised with its
    ID so the caller can surface it.
    """
