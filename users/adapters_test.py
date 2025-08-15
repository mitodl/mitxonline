"""Tests for the SCIM adapters."""

from uuid import uuid4

import faker
import pytest

from b2b.constants import CONTRACT_INTEGRATION_NONSSO, CONTRACT_INTEGRATION_SSO
from b2b.factories import ContractPageFactory
from users.adapters import LearnUserAdapter, UserAdapter
from users.factories import UserFactory

pytestmark = pytest.mark.django_db
FAKE = faker.Faker()


def test_user_adapter_blank_fields():
    """Test that an incoming request with no name data doesn't blank out fields"""
    user = UserFactory.create(
        name="Joe Smith",
        legal_address__first_name="Joe",
        legal_address__last_name="Smith",
    )

    adapter = UserAdapter(user)
    adapter.from_dict(
        {
            "active": True,
            "userName": "jsmith",
            "externalId": "1",
        }
    )
    adapter.save()

    user.refresh_from_db()

    assert user.name == "Joe Smith"
    assert user.legal_address.first_name == "Joe"
    assert user.legal_address.last_name == "Smith"


@pytest.mark.parametrize(
    "create_user_first",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "add_to_sso_contract",
    [
        True,
        False,
    ],
)
def test_user_adapter_groups(create_user_first, add_to_sso_contract):
    """
    Make sure the groups that are being sent over get mapped correctly.

    The organization data gets thrown into the groups attribute. So, we should
    make sure that the groups get parsed out and the user's contracts are
    adjusted as we expect.
    """

    contract = ContractPageFactory.create(
        integration_type=CONTRACT_INTEGRATION_SSO,
    )
    non_sso_contract = ContractPageFactory.create(
        integration_type=CONTRACT_INTEGRATION_NONSSO,
    )

    scim_dict = {
        "active": True,
        "userName": FAKE.user_name(),
        "externalId": uuid4(),
        "groups": [
            {
                "value": uuid4(),
                "display": "Students",
                "type": "direct",
            },
            {
                "value": uuid4(),
                "display": contract.organization.org_key,
                "type": "organization",
            },
            {
                "value": uuid4(),
                "display": "Staff",
                "type": "direct",
            },
        ],
    }

    if create_user_first:
        user = UserFactory.create()
        user.b2b_contracts.add(non_sso_contract)
    else:
        user = UserFactory.build()

    if create_user_first and add_to_sso_contract:
        other_contract = ContractPageFactory.create(
            integration_type=CONTRACT_INTEGRATION_SSO
        )
        user.b2b_contracts.add(other_contract)

    adapter = LearnUserAdapter(user)

    adapter.from_dict(scim_dict)
    adapter.save()

    user.refresh_from_db()
    assert user.b2b_contracts.filter(pk=contract.id).exists()

    if create_user_first and add_to_sso_contract:
        assert not user.b2b_contracts.filter(pk=other_contract.id).exists()
