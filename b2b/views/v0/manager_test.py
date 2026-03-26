"""Tests for the B2B Manager views"""

import pytest
import reversion
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_MEMBERSHIP_CODE
from b2b.factories import ContractPageFactory
from b2b.models import UserOrganization
from courses.factories import CourseRunFactory
from ecommerce.factories import ProductFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def org_setup():
    """
    Generate a basic B2B org setup for these tests.

    Creates a user to act as manager, a handful of contracts, some organizations,
    some course runs, and the associations for that. Specifically:
    - A manager user (which is a regular user otherwise, not a superuser)
    - Two contracts in a single organization
        - Both contracts are "code" type, so will generate enrollment codes
        - First contract is seat-limited to 20, the second is unlimited
    - An attachment for the manager user to that org, with the "is_manager" flag set
    - Two course runs with products for each contract
    - A third contract in a separate organization, of "code" type with 20 seats
    - Two course runs with products in the third contract

    This will assert that the correct number of discount codes are created for
    each contract.

    It then returns these items back so they can be used in tests. This is a
    tuple containing:
    - manager_user
    - tuple of organizations
    - tuple for each contract containing
        - contract
        - tuple of (course run, product) for each run/product
    """

    manager_user = UserFactory.create()

    # Contract/org creation

    contract_1 = ContractPageFactory.create(
        integration_type=CONTRACT_MEMBERSHIP_CODE,
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=20,
    )
    contract_2 = ContractPageFactory.create(
        integration_type=CONTRACT_MEMBERSHIP_CODE,
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=0,
        organization=contract_1.organization,
    )
    UserOrganization.objects.create(
        user=manager_user,
        organization=contract_1.organization,
        keep_until_seen=True,
        is_manager=True,
    )

    contract_3 = ContractPageFactory.create(
        integration_type=CONTRACT_MEMBERSHIP_CODE,
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=20,
    )

    # Course run and products creation

    contract_1_run_1 = CourseRunFactory.create(b2b_contract=contract_1)
    contract_1_run_2 = CourseRunFactory.create(b2b_contract=contract_1)

    with reversion.create_revision():
        contract_1_run_1_product = ProductFactory.create(
            purchasable_object=contract_1_run_1
        )
        contract_1_run_2_product = ProductFactory.create(
            purchasable_object=contract_1_run_2
        )

    contract_2_run_1 = CourseRunFactory.create(b2b_contract=contract_2)
    contract_2_run_2 = CourseRunFactory.create(b2b_contract=contract_2)

    with reversion.create_revision():
        contract_2_run_1_product = ProductFactory.create(
            purchasable_object=contract_2_run_1
        )
        contract_2_run_2_product = ProductFactory.create(
            purchasable_object=contract_2_run_2
        )

    contract_3_run_1 = CourseRunFactory.create(b2b_contract=contract_3)
    contract_3_run_2 = CourseRunFactory.create(b2b_contract=contract_3)

    with reversion.create_revision():
        contract_3_run_1_product = ProductFactory.create(
            purchasable_object=contract_3_run_1
        )
        contract_3_run_2_product = ProductFactory.create(
            purchasable_object=contract_3_run_2
        )

    # Enrollment code creation
    # For contracts 1 and 3, we should end up with 40 codes total - 20 for
    # each course run. For contract 2, we should end up with 2 codes.

    created, updated, errored = ensure_enrollment_codes_exist(contract_1)

    assert created == 40
    assert updated == 0
    assert errored == 0

    created, updated, errored = ensure_enrollment_codes_exist(contract_2)

    assert created == 2
    assert updated == 0
    assert errored == 0

    created, updated, errored = ensure_enrollment_codes_exist(contract_3)

    assert created == 40
    assert updated == 0
    assert errored == 0

    return (
        manager_user,
        (contract_1.organization, contract_3.organization),
        (
            contract_1,
            (
                contract_1_run_1,
                contract_1_run_1_product,
            ),
            (
                contract_1_run_2,
                contract_1_run_2_product,
            ),
        ),
        (
            contract_2,
            (
                contract_2_run_1,
                contract_2_run_1_product,
            ),
            (
                contract_2_run_2,
                contract_2_run_2_product,
            ),
        ),
        (
            contract_3,
            (
                contract_3_run_1,
                contract_3_run_1_product,
            ),
            (
                contract_3_run_2,
                contract_3_run_2_product,
            ),
        ),
    )


@pytest.fixture
def manager_drf_client(org_setup):
    """Return an APIClient set up with the manager account."""

    client = APIClient()
    client.force_login(org_setup[0])

    return client


def test_org_setup(org_setup):
    """Very basic test that the org setup worked as expected"""

    assert len(org_setup) == 5


def test_org_contract_lists(org_setup, manager_drf_client):
    """Test that the org and contract list pages work as expected"""

    _, orgs, contract_1, contract_2, contract_3 = org_setup

    manager_org_list = reverse("b2b:b2b-manager-organization")

    resp = manager_drf_client.get(manager_org_list)

    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == orgs[0].id

    manager_contract_list = reverse(
        "b2b:b2b-manager-org-contract-list",
        kwargs={"parent_lookup_organization": orgs[0].id},
    )

    resp = manager_drf_client.get(manager_contract_list)

    assert resp.status_code == status.HTTP_200_OK
    resp_json = resp.json()

    assert len(resp_json["contracts"]) == 2

    manager_contract_list = reverse(
        "b2b:b2b-manager-org-contract-list",
        kwargs={"parent_lookup_organization": orgs[1].id},
    )

    assert resp.status_code == status.HTTP_403_FORBIDDEN
