"""Tests for the B2B management command helpers."""

import pytest
from django.core.management import CommandError

from b2b.factories import ContractPageFactory
from b2b.management.utils import get_contract_by_id_or_slug

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("field", ["id", "slug"])
def test_get_contract_by_id_or_slug(field):
    """A contract is found by its numeric ID or by its slug."""
    contract = ContractPageFactory.create()

    assert get_contract_by_id_or_slug(str(getattr(contract, field))) == contract


def test_get_contract_by_id_or_slug_not_found():
    """An identifier that matches no contract returns None."""
    ContractPageFactory.create()

    assert get_contract_by_id_or_slug("nonexistent") is None


def test_get_contract_by_id_or_slug_rejects_ambiguous_slug():
    """A slug shared by contracts in two organizations raises instead of picking one."""
    contract = ContractPageFactory.create()
    other = ContractPageFactory.create(slug=contract.slug)

    with pytest.raises(CommandError) as excinfo:
        get_contract_by_id_or_slug(contract.slug)

    assert str(contract.id) in str(excinfo.value)
    assert str(other.id) in str(excinfo.value)
