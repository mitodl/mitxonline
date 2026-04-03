"""Tests for the B2B Manager views"""

import pytest
import reversion
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_MEMBERSHIP_CODE
from b2b.factories import ContractPageFactory
from b2b.models import DiscountContractAttachmentRedemption, UserOrganization
from b2b.serializers.v0 import (
    BaseContractPageSerializer,
)
from b2b.serializers.v0.manager import ManagerEnrollmentSerializer
from courses.factories import CourseRunFactory
from courses.models import CourseRunEnrollment
from ecommerce.factories import ProductFactory
from main.test_utils import assert_drf_json_equal
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def mock_hubspot(mocker):
    """Mock out some hubspot stuff"""

    mocker.patch("hubspot_sync.task_helpers.sync_hubspot_user")
    mocker.patch("hubspot_sync.tasks.sync_contact_with_hubspot.delay")


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

    manager_org_list = reverse("b2b:b2b-manager-organization-list")

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

    assert len(resp_json) == 2
    assert_drf_json_equal(
        resp_json,
        BaseContractPageSerializer([contract_1[0], contract_2[0]], many=True).data,
        ignore_order=True,
    )
    assert contract_3[0].id not in [contract["id"] for contract in resp_json]

    manager_contract_list = reverse(
        "b2b:b2b-manager-org-contract-list",
        kwargs={"parent_lookup_organization": orgs[1].id},
    )

    resp = manager_drf_client.get(manager_contract_list)

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_org_contract_run_list(org_setup, manager_drf_client):
    """Test that we can get the course runs out of the contract as expected."""

    # Extracting just the stuff we want.
    _, _, contract_1, _, contract_3 = org_setup
    contract, *runs = contract_1
    runs = [run[0] for run in runs]

    manager_contract_run_list = reverse(
        "b2b:b2b-manager-org-contract-course-runs",
        kwargs={
            "parent_lookup_organization": contract.organization.id,
            "pk": contract.id,
        },
    )

    resp = manager_drf_client.get(manager_contract_run_list)
    assert resp.status_code == status.HTTP_200_OK

    assert len(resp.json()) == 2
    assert sorted([run.readable_id for run in runs]) == sorted(
        [run["readable_id"] for run in resp.json()]
    )

    contract, *_ = contract_3

    manager_contract_run_list = reverse(
        "b2b:b2b-manager-org-contract-course-runs",
        kwargs={
            "parent_lookup_organization": contract.organization.id,
            "pk": contract.id,
        },
    )

    resp = manager_drf_client.get(manager_contract_run_list)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_org_contract_run_enrollments(org_setup, manager_drf_client):
    """Test that we can get enrollments in a contract run."""

    # Extracting just the stuff we want.
    _, _, contract_1, _, contract_3 = org_setup
    contract, *runs = contract_1
    runs = [run[0] for run in runs]

    users_to_enroll = UserFactory.create_batch(3)

    run_enrollments = [
        [
            CourseRunEnrollment.objects.create(
                user=users_to_enroll[0],
                run=runs[0],
            ),
            CourseRunEnrollment.objects.create(
                user=users_to_enroll[1],
                run=runs[0],
            ),
        ],
        [
            CourseRunEnrollment.objects.create(
                user=users_to_enroll[2],
                run=runs[1],
            )
        ],
    ]

    for idx, run in enumerate(runs):
        manager_contract_enrol_list = reverse(
            "b2b:b2b-manager-org-contract-course-run-enrollments",
            kwargs={
                "parent_lookup_organization": contract.organization.id,
                "pk": contract.id,
                "course_run_id": run.courseware_id,
            },
        )

        resp = manager_drf_client.get(manager_contract_enrol_list)
        assert resp.status_code == status.HTTP_200_OK

        assert len(resp.json()) == len(run_enrollments[idx])
        assert_drf_json_equal(
            resp.json(),
            ManagerEnrollmentSerializer(run_enrollments[idx], many=True).data,
            ignore_order=True,
        )

    contract, *runs = contract_3
    run = runs[0][0]

    manager_contract_enrol_list = reverse(
        "b2b:b2b-manager-org-contract-course-run-enrollments",
        kwargs={
            "parent_lookup_organization": contract.organization.id,
            "pk": contract.id,
            "course_run_id": run.courseware_id,
        },
    )

    resp = manager_drf_client.get(manager_contract_enrol_list)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_org_contract_codes(org_setup, manager_drf_client):
    """Test that we can retrieve codes as expected."""

    _, _, (contract_1, *_), (contract_2, *_), (contract_3, *_) = org_setup
    some_users = UserFactory.create_batch(3)

    for contract in [contract_1, contract_2]:
        # Sanity checks. We should have more discounts than max_learners, because
        # _total_ we should have max_learners * course run count discounts.
        discount_count = contract.get_discounts().count()
        assert discount_count > contract.max_learners

        expected_code_count = contract.max_learners if contract.max_learners > 0 else 1
        contract_codes = [
            discount.discount_code
            for discount in contract.get_discounts()
            .order_by("id")
            .all()[:expected_code_count]
        ]

        # Pull the codes - we should get max_learner codes back and they should
        # match the sorting order above.

        manager_contract_code_list = reverse(
            "b2b:b2b-manager-org-contract-codes",
            kwargs={
                "parent_lookup_organization": contract.organization.id,
                "pk": contract.id,
            },
        )

        resp = manager_drf_client.get(manager_contract_code_list)
        assert resp.status_code == status.HTTP_200_OK

        resp_codes = [resp_code["code"] for resp_code in resp.json()]
        assert len(resp_codes) == expected_code_count

        assert contract_codes == resp_codes

        # Do it again - since we're providing a subset of the codes, it should
        # be the _same_ codes each time.

        resp = manager_drf_client.get(manager_contract_code_list)
        assert resp.status_code == status.HTTP_200_OK

        resp_codes = [resp_code["code"] for resp_code in resp.json()]

        assert len(resp_codes) == expected_code_count
        assert contract_codes == resp_codes

        # Create some redemptions. The API/etc only considers attachment
        # redemptions to count; enrollment (order) redemptions don't matter here.
        # Use discounts from the end of the list to make it easier to check that
        # the subset of discounts hasn't changed.

        if contract.max_learners > 1:
            discounts_to_use = contract.get_discounts().order_by("-id")[:3]
        else:
            # This is the unlimited seat one, so just use the same discount 3 times.
            discount_to_use = contract.get_discounts().order_by("id").last()
            discounts_to_use = [discount_to_use, discount_to_use, discount_to_use]

        for idx, user in enumerate(some_users):
            DiscountContractAttachmentRedemption.objects.create(
                discount=discounts_to_use[idx], user=user, contract=contract
            )

        resp = manager_drf_client.get(manager_contract_code_list)
        assert resp.status_code == status.HTTP_200_OK

        resp_codes = [resp_code["code"] for resp_code in resp.json()]

        if contract.max_learners > 1:
            assert len(resp_codes) == expected_code_count

            # The redeemed codes should be at the top, followed by the same set we
            # had before (up to the end of the list)
            used_codes = [discount.discount_code for discount in discounts_to_use]
            assert sorted(used_codes) == sorted(resp_codes[:3])
            assert resp_codes[3:] == contract_codes[:17]

            assert resp.json()[0]["is_redeemed"]
            assert not resp.json()[3]["is_redeemed"]
        else:
            # For the unlimited seat one, we only get back the single code.

            assert len(resp_codes) == 1

    manager_contract_code_list = reverse(
        "b2b:b2b-manager-org-contract-codes",
        kwargs={
            "parent_lookup_organization": contract_3.organization.id,
            "pk": contract_3.id,
        },
    )
    resp = manager_drf_client.get(manager_contract_code_list)
    assert resp.status_code == status.HTTP_403_FORBIDDEN
