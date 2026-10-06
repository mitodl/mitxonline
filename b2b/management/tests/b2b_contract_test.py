"""Tests for the b2b_contract command."""

import pytest

from b2b.constants import CONTRACT_MEMBERSHIP_MANAGED
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.management.commands import b2b_contract

pytestmark = [pytest.mark.django_db]


def test_import_contract_ignores_same_slug_in_another_org():
    """Importing creates the contract in its org even if another org uses the slug."""
    elsewhere = ContractPageFactory.create()
    org = OrganizationPageFactory.create()

    contract = b2b_contract.Command()._import_contract(  # noqa: SLF001
        org,
        {"name": "Imported", "membership_type": CONTRACT_MEMBERSHIP_MANAGED},
        elsewhere.slug,
    )

    assert contract.id != elsewhere.id
    assert contract.organization == org
