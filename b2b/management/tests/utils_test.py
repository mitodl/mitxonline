"""Tests for the B2B management command helpers."""

import pytest
from django.core.management import CommandError

from b2b.factories import ContractPageFactory
from b2b.management.utils import get_contract_by_id_or_slug

pytestmark = [pytest.mark.django_db]


def test_get_contract_by_id_or_slug_rejects_ambiguous_slug():
    """A slug shared by contracts in two organizations raises instead of picking one."""
    contract = ContractPageFactory.create()
    other = ContractPageFactory.create(slug=contract.slug)

    with pytest.raises(CommandError) as excinfo:
        get_contract_by_id_or_slug(contract.slug)

    assert str(contract.id) in str(excinfo.value)
    assert str(other.id) in str(excinfo.value)
