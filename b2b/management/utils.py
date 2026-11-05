"""Helpers shared by management commands that work with B2B data."""

from django.core.management import CommandError
from django.core.management.color import color_style

from b2b.models import ContractPage


def get_contract_by_id_or_slug(identifier: str) -> ContractPage | None:
    """
    Return the contract with this numeric ID or slug, or None if there isn't one.

    Wagtail only enforces slug uniqueness among sibling pages, so contracts in
    different organizations can share a slug. An ambiguous slug raises
    CommandError listing the matches rather than picking one.
    """

    if identifier.isdecimal():
        return ContractPage.objects.filter(id=identifier).first()

    contracts = list(
        ContractPage.objects.filter(slug=identifier)
        .select_related("organization")
        .order_by("id")
    )
    if len(contracts) > 1:
        matches = "\n".join(
            f"  {contract.id} ({contract.organization.name})" for contract in contracts
        )
        msg = (
            f"Contract slug '{identifier}' matches more than one contract:\n"
            f"{matches}\n"
            "Pass the contract ID instead."
        )
        raise CommandError(color_style().WARNING(msg))

    return contracts[0] if contracts else None
