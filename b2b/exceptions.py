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
