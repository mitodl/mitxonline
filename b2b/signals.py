"""Signals for the B2B app."""

from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from b2b.models import ContractPage, UserB2BContract
from users.models import User


@receiver(
    m2m_changed,
    sender=UserB2BContract,
    dispatch_uid="user_b2b_contracts_upgrade_enrollments",
)
def upgrade_enrollments_on_contract_attach(
    sender,  # noqa: ARG001
    instance,
    action,
    pk_set,
    *,
    reverse,
    **kwargs,  # noqa: ARG001
):
    """
    Upgrade audit enrollments when a user is attached to contracts.

    Users are attached through ``user.b2b_contracts.add(...)`` from a few
    places (Keycloak org reconciliation, enrollment codes, B2B purchases), so
    this catches all of them. ``pk_set`` on post_add only holds the newly
    created links, so contracts the user was already in are skipped.
    """
    from b2b.api import upgrade_user_enrollments_for_contracts  # noqa: PLC0415

    if action != "post_add" or not pk_set:
        return

    if reverse:
        # instance is a ContractPage, pk_set holds the User ids being added
        for user in User.objects.filter(pk__in=pk_set):
            upgrade_user_enrollments_for_contracts(user, [instance])
        return

    # instance is a User, pk_set holds the ContractPage ids being added
    upgrade_user_enrollments_for_contracts(
        instance, ContractPage.objects.filter(pk__in=pk_set)
    )
