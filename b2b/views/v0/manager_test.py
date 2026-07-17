"""Tests for the B2B Manager views"""

import pytest
import reversion
from django.urls import reverse
from mitol.common.utils.datetime import now_in_utc
from rest_framework import status
from rest_framework.test import APIClient

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_MEMBERSHIP_CODE
from b2b.factories import ContractPageFactory
from b2b.models import (
    REDEMPTION_STATUS_ASSIGNED,
    REDEMPTION_STATUS_REDEEMED,
    REDEMPTION_STATUS_UNASSIGNED,
    DiscountContractAttachmentRedemption,
    UserOrganization,
)
from b2b.serializers.v0 import (
    BaseContractPageSerializer,
)
from b2b.serializers.v0.manager import ManagerEnrollmentSerializer
from b2b.views.v0.manager import CodeAssignment, assign_codes_and_send_emails
from courses.factories import CourseRunFactory
from courses.models import CourseRunEnrollment
from ecommerce.constants import REDEMPTION_TYPE_ONE_TIME
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
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=20,
    )
    contract_2 = ContractPageFactory.create(
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
    assert len(resp.json()["results"]) == 1
    assert resp.json()["results"][0]["id"] == orgs[0].id

    manager_contract_list = reverse(
        "b2b:b2b-manager-org-contract-list",
        kwargs={"parent_lookup_organization": orgs[0].id},
    )

    resp = manager_drf_client.get(manager_contract_list)

    assert resp.status_code == status.HTTP_200_OK
    resp_json = resp.json()["results"]

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

    assert len(resp.json()["results"]) == 2
    assert sorted([run.readable_id for run in runs]) == sorted(
        [run["readable_id"] for run in resp.json()["results"]]
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
                user=users_to_enroll[0],
                run=runs[1],
            ),
            CourseRunEnrollment.objects.create(
                user=users_to_enroll[1],
                run=runs[1],
            ),
            CourseRunEnrollment.objects.create(
                user=users_to_enroll[2],
                run=runs[1],
            ),
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

        assert len(resp.json()["results"]) == len(run_enrollments[idx])
        assert_drf_json_equal(
            resp.json()["results"],
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

        # We don't expect to get anything back since we have no redeemed or
        # assigned codes yet, regardless of max_learners.

        manager_contract_code_list = reverse(
            "b2b:b2b-manager-org-contract-codes",
            kwargs={
                "parent_lookup_organization": contract.organization.id,
                "pk": contract.id,
            },
        )

        resp = manager_drf_client.get(manager_contract_code_list)
        assert resp.status_code == status.HTTP_200_OK

        resp_codes = [resp_code["code"] for resp_code in resp.json()["results"]]
        assert resp_codes == []

        # Create some redemptions. The API/etc only considers attachment
        # redemptions to count; enrollment (order) redemptions don't matter here.
        # Use discounts from the end of the list to make it easier to check that
        # the subset of discounts hasn't changed.

        if contract.max_learners > 1:
            redeemed_and_assigned_count = 1 + len(some_users)
            discounts_to_use = contract.get_discounts().order_by("-id")[:3]

            # Create one "assigned" redemption (pre-assigned but not yet claimed)
            # using a different discount so all three statuses appear in the response.
            assigned_discount = contract.get_discounts().order_by("id").first()
            DiscountContractAttachmentRedemption.objects.create(
                discount=assigned_discount,
                assigned_email="assigned@example.com",
                contract=contract,
            )
        else:
            # This is the unlimited seat one, so just use the same discount 3 times.
            discount_to_use = contract.get_discounts().order_by("id").last()
            discounts_to_use = [discount_to_use, discount_to_use, discount_to_use]
            redeemed_and_assigned_count = len(some_users)

        for idx, user in enumerate(some_users):
            DiscountContractAttachmentRedemption.objects.create(
                discount=discounts_to_use[idx], user=user, contract=contract
            )

        resp = manager_drf_client.get(manager_contract_code_list)
        assert resp.status_code == status.HTTP_200_OK

        resp_codes = [resp_code["code"] for resp_code in resp.json()["results"]]

        if contract.max_learners > 1:
            assert len(resp_codes) == redeemed_and_assigned_count

            # All codes with redemptions (redeemed and assigned) must appear in
            # the response.
            used_codes = {discount.discount_code for discount in discounts_to_use}
            assert used_codes.issubset(set(resp_codes))
            assert assigned_discount.discount_code in resp_codes

            # Verify all non-unassigned redemption statuses are represented in the response.
            response_statuses = {
                code["redemption_status"] for code in resp.json()["results"]
            }
            assert REDEMPTION_STATUS_REDEEMED in response_statuses
            assert REDEMPTION_STATUS_ASSIGNED in response_statuses
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


def test_org_contract_codes_redeemed_by_differs_from_assigned_to(
    org_setup, manager_drf_client, mocker
):
    """
    redeemed_by should reflect the redeeming user's email, not the email the
    code was originally assigned to, when those two addresses differ.
    """
    mocker.patch("b2b.models.OrganizationPage.attach_user", return_value=True)

    _, _, (contract_1, *_), *_ = org_setup

    # Pick a code that has not yet been redeemed.
    discount = contract_1.get_discounts().order_by("id").first()

    # A learner whose email differs from the assignee who will redeems the code.
    redeeming_user = UserFactory.create(email="redeemer@example.com")
    learner_client = APIClient()
    learner_client.force_login(redeeming_user)

    # This test will change a bit once we have an assign endpoint. Once implemented:
    # - We'll assign the code to an email address via forthcoming API
    # - We'll attach/redeem the code to whoever is logged in, which in this case will be the user with a different email address
    # - We'll verify that the codes endpoint reflects the difference between the assgined email and the redeeming user's email

    attach_url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": discount.discount_code}
    )
    attach_resp = learner_client.post(attach_url)
    assert attach_resp.status_code == status.HTTP_201_CREATED

    dcar = DiscountContractAttachmentRedemption.objects.get(
        discount=discount, user=redeeming_user
    )
    dcar.assigned_email = "assignee@example.com"
    dcar.save()

    # The manager fetches the codes list.
    manager_contract_code_list = reverse(
        "b2b:b2b-manager-org-contract-codes",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )
    resp = manager_drf_client.get(manager_contract_code_list)
    assert resp.status_code == status.HTTP_200_OK

    redeemed_code = next(
        code
        for code in resp.json()["results"]
        if code["code"] == discount.discount_code
    )
    assert redeemed_code["assigned_to"] == "assignee@example.com"
    assert redeemed_code["redeemed_by"] == "redeemer@example.com"


def test_org_contract_detail_no_max_learners(org_setup, manager_drf_client):
    """
    The detail endpoint should not error when max_learners is None, and
    should report total/unassigned codes as None (not a meaningful metric
    without a learner cap) regardless of how many codes have been assigned
    or redeemed.
    """
    _, _, (contract_1, *_), *_ = org_setup

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=None,
        organization=contract_1.organization,
    )
    run = CourseRunFactory.create(b2b_contract=contract)
    with reversion.create_revision():
        ProductFactory.create(purchasable_object=run)

    created, updated, errored = ensure_enrollment_codes_exist(contract)
    assert created == 1
    assert updated == 0
    assert errored == 0

    detail_url = reverse(
        "b2b:b2b-manager-org-contract-detail",
        kwargs={
            "parent_lookup_organization": contract.organization.id,
            "pk": contract.id,
        },
    )

    resp = manager_drf_client.get(detail_url)
    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert resp_data["total_codes"] is None
    assert resp_data["assigned_codes"] == 0
    assert resp_data["unassigned_codes"] is None
    assert resp_data["redeemed_codes"] == 0

    # Redeem the one code that exists, and confirm the breakdown still makes
    # sense (and doesn't error) with a real redemption in play.
    discount = contract.get_discounts().order_by("id").first()
    redeemer = UserFactory.create()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract,
        user=redeemer,
    )

    resp = manager_drf_client.get(detail_url)
    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert resp_data["total_codes"] is None
    assert resp_data["assigned_codes"] == 0
    assert resp_data["unassigned_codes"] is None
    assert resp_data["redeemed_codes"] == 1

    # /codes should show the single code that exists for this contract.
    codes_url = reverse(
        "b2b:b2b-manager-org-contract-codes",
        kwargs={
            "parent_lookup_organization": contract.organization.id,
            "pk": contract.id,
        },
    )

    resp = manager_drf_client.get(codes_url)
    assert resp.status_code == status.HTTP_200_OK

    resp_results = resp.json()["results"]
    assert len(resp_results) == 1
    assert resp_results[0]["code"] == discount.discount_code


# ---------------------------------------------------------------------------
# codes search_term tests
# ---------------------------------------------------------------------------


def _get_codes_for_search(client, url, search):
    resp = client.get(url, {"search_term": search})
    assert resp.status_code == status.HTTP_200_OK
    return {r["code"] for r in resp.json()["results"]}


def test_org_contract_codes_search_term(org_setup, manager_drf_client):
    """search_term filters codes by assigned_email, user email, user name, and assigned_name."""
    _, _, (contract_1, *_), *_ = org_setup

    discounts = list(contract_1.get_discounts().order_by("id")[:4])

    user_a = UserFactory.create(email="alice@example.com", name="Alice Smith")
    user_b = UserFactory.create(email="bob@example.com", name="Bob Jones")

    # assigned_email only (not yet redeemed)
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[0],
        assigned_email="carol@example.com",
        assigned_name="Carol White",
        contract=contract_1,
    )
    # redeemed by user_a (search via user email and name)
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[1],
        user=user_a,
        contract=contract_1,
    )
    # redeemed by user_b (search via assigned_name on a redeemed code)
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[2],
        user=user_b,
        assigned_name="Bobby Jones",
        contract=contract_1,
    )

    url = reverse(
        "b2b:b2b-manager-org-contract-codes",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    # Match by assigned_email
    assert _get_codes_for_search(manager_drf_client, url, "carol") == {
        discounts[0].discount_code
    }

    # Match by assigned_name
    assert _get_codes_for_search(manager_drf_client, url, "Carol White") == {
        discounts[0].discount_code
    }

    # Match by user email
    assert _get_codes_for_search(manager_drf_client, url, "alice") == {
        discounts[1].discount_code
    }

    # Match by user name
    assert _get_codes_for_search(manager_drf_client, url, "Alice Smith") == {
        discounts[1].discount_code
    }

    # Match by assigned_name on a redeemed code
    assert _get_codes_for_search(manager_drf_client, url, "Bobby") == {
        discounts[2].discount_code
    }

    # No match returns empty
    assert _get_codes_for_search(manager_drf_client, url, "zzznomatch") == set()

    # No search_term returns all codes (up to max_learners)
    resp = manager_drf_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()["results"]) == 3


# ---------------------------------------------------------------------------
# codes status filter tests
# ---------------------------------------------------------------------------


def _get_codes_for_status(client, url, status_value):
    resp = client.get(url, {"status": status_value})
    assert resp.status_code == status.HTTP_200_OK
    return {r["code"] for r in resp.json()["results"]}


def test_org_contract_codes_status_filter(org_setup, manager_drf_client):
    """Status filter returns only codes matching the requested redemption status."""
    _, _, (contract_1, *_), *_ = org_setup

    discounts = list(contract_1.get_discounts().order_by("id")[:3])

    user_a = UserFactory.create(email="alice@example.com")

    # assigned only (no user, no redeemed_on)
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[0],
        assigned_email="carol@example.com",
        contract=contract_1,
    )
    # redeemed (has user)
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[1],
        user=user_a,
        contract=contract_1,
    )
    # redeemed (has redeemed_on but no user, e.g. user deleted)
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[2],
        redeemed_on=now_in_utc(),
        contract=contract_1,
    )

    url = reverse(
        "b2b:b2b-manager-org-contract-codes",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    assert _get_codes_for_status(
        manager_drf_client, url, REDEMPTION_STATUS_ASSIGNED
    ) == {discounts[0].discount_code}

    assert _get_codes_for_status(
        manager_drf_client, url, REDEMPTION_STATUS_REDEEMED
    ) == {
        discounts[1].discount_code,
        discounts[2].discount_code,
    }


def test_org_contract_codes_status_and_search_combined(org_setup, manager_drf_client):
    """Status and search_term filters can be combined."""
    _, _, (contract_1, *_), *_ = org_setup

    discounts = list(contract_1.get_discounts().order_by("id")[:3])

    user_a = UserFactory.create(email="alice@example.com", name="Alice Smith")
    user_b = UserFactory.create(email="bob@example.com", name="Bob Jones")

    # assigned to alice email but not redeemed
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[0],
        assigned_email="alice@example.com",
        contract=contract_1,
    )
    # redeemed by user_a
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[1],
        user=user_a,
        contract=contract_1,
    )
    # redeemed by user_b
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[2],
        user=user_b,
        contract=contract_1,
    )

    url = reverse(
        "b2b:b2b-manager-org-contract-codes",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    # assigned + search matching alice: only the unredemed code
    resp = manager_drf_client.get(
        url, {"status": REDEMPTION_STATUS_ASSIGNED, "search_term": "alice"}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert {r["code"] for r in resp.json()["results"]} == {discounts[0].discount_code}

    # redeemed + search matching alice: only user_a's redeemed code
    resp = manager_drf_client.get(
        url, {"status": REDEMPTION_STATUS_REDEEMED, "search_term": "alice"}
    )
    assert resp.status_code == status.HTTP_200_OK
    assert {r["code"] for r in resp.json()["results"]} == {discounts[1].discount_code}


# ---------------------------------------------------------------------------
# assign_code tests
# ---------------------------------------------------------------------------


def test_assign_code(org_setup, manager_drf_client, mocker):
    """A manager can assign an unassigned code to an email address."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    code = discount.discount_code

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": code,
        },
    )

    resp = manager_drf_client.post(
        assign_url,
        data={"email": "learner@example.com", "name": "Test Learner"},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK

    redemption = DiscountContractAttachmentRedemption.objects.get(
        discount=discount, assigned_email="learner@example.com"
    )
    assert redemption.assigned_name == "Test Learner"
    mock_task.delay.assert_called_once_with([redemption.id])

    resp_data = resp.json()
    assert resp_data["code"] == code
    assert resp_data["redemption_status"] == REDEMPTION_STATUS_ASSIGNED
    assert resp_data["assigned_to"] == "learner@example.com"
    assert resp_data["assigned_name"] == "Test Learner"


def test_assign_code_name_defaults_to_empty(org_setup, manager_drf_client, mocker):
    """Assigning a code without a name stores an empty string for assigned_name."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(
        assign_url, data={"email": "learner@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_200_OK
    assert DiscountContractAttachmentRedemption.objects.filter(
        discount=discount, assigned_email="learner@example.com", assigned_name=""
    ).exists()


def test_assign_code_invalid_request(org_setup, manager_drf_client):
    """assign_code returns 400 when the request body is missing the required email field."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(assign_url, data={"name": "No Email"}, format="json")

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_assign_code_not_found(org_setup, manager_drf_client):
    """assign_code returns 404 when the code does not belong to the contract."""
    _, _, (contract_1, *_), *_ = org_setup

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": "nonexistent-code",
        },
    )

    resp = manager_drf_client.post(
        assign_url, data={"email": "learner@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_assign_code_already_assigned(org_setup, manager_drf_client):
    """assign_code returns 409 when the code already has a redemption record."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="existing@example.com",
    )

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(
        assign_url, data={"email": "new@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_409_CONFLICT


def test_assign_code_forbidden(org_setup, manager_drf_client):
    """A manager cannot assign codes in a contract belonging to an org they don't manage."""
    _, _, *_, (contract_3, *_) = org_setup

    discount = contract_3.get_discounts().order_by("id").first()

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_3.organization.id,
            "pk": contract_3.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(
        assign_url, data={"email": "learner@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_assign_code_internal_error(org_setup, manager_drf_client, mocker):
    """assign_code returns 500 when the assignment DB operation fails."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    mocker.patch(
        "b2b.views.v0.manager.assign_codes_and_send_emails", return_value=False
    )
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()

    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(
        assign_url, data={"email": "learner@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# revoke_code tests
# ---------------------------------------------------------------------------


def test_revoke_code(org_setup, manager_drf_client):
    """A manager can revoke an assigned code, deleting its redemption record."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    original_code = discount.discount_code
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="assignee@example.com",
        assigned_name="Assignee",
    )

    revoke_url = reverse(
        "b2b:b2b-manager-org-contract-revoke-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.delete(revoke_url)

    assert resp.status_code == status.HTTP_200_OK
    assert not DiscountContractAttachmentRedemption.objects.filter(
        discount=discount, assigned_email="assignee@example.com"
    ).exists()

    resp_data = resp.json()
    assert resp_data["code"] != original_code
    assert resp_data["redemption_status"] == REDEMPTION_STATUS_UNASSIGNED


def test_revoke_code_not_found(org_setup, manager_drf_client):
    """revoke_code returns 404 when the code does not belong to the contract."""
    _, _, (contract_1, *_), *_ = org_setup

    revoke_url = reverse(
        "b2b:b2b-manager-org-contract-revoke-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": "nonexistent-code",
        },
    )

    resp = manager_drf_client.delete(revoke_url)

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_revoke_code_assignment_not_found(org_setup, manager_drf_client):
    """revoke_code returns 404 when the code has no assignment."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()

    revoke_url = reverse(
        "b2b:b2b-manager-org-contract-revoke-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.delete(revoke_url)

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_revoke_code_already_redeemed(org_setup, manager_drf_client):
    """revoke_code returns 409 when the code has already been redeemed by a user."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    redeemer = UserFactory.create()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="assignee@example.com",
        user=redeemer,
    )

    revoke_url = reverse(
        "b2b:b2b-manager-org-contract-revoke-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.delete(revoke_url)

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "detail" in resp.json()
    assert DiscountContractAttachmentRedemption.objects.filter(
        discount=discount, user=redeemer
    ).exists()


def test_revoke_code_forbidden(org_setup, manager_drf_client):
    """A manager cannot revoke codes in a contract belonging to an org they don't manage."""
    _, _, *_, (contract_3, *_) = org_setup

    discount = contract_3.get_discounts().order_by("id").first()

    revoke_url = reverse(
        "b2b:b2b-manager-org-contract-revoke-code",
        kwargs={
            "parent_lookup_organization": contract_3.organization.id,
            "pk": contract_3.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.delete(revoke_url)

    assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# send_reminder_for_code_assignment tests
# ---------------------------------------------------------------------------


def test_send_reminder_for_code_assignment(org_setup, manager_drf_client, mocker):
    """A manager can send a reminder email for an assigned but unclaimed code."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    redemption = DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="assignee@example.com",
    )

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(remind_url, format="json")

    assert resp.status_code == status.HTTP_200_OK
    mock_task.delay.assert_called_once_with([redemption.id])

    resp_data = resp.json()
    assert resp_data["code"] == discount.discount_code
    assert resp_data["redemption_status"] == REDEMPTION_STATUS_ASSIGNED


def test_send_reminder_code_not_found(org_setup, manager_drf_client):
    """send_reminder returns 404 when the code does not belong to the contract."""
    _, _, (contract_1, *_), *_ = org_setup

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": "nonexistent-code",
        },
    )

    resp = manager_drf_client.post(
        remind_url, data={"email": "assignee@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_send_reminder_assignment_not_found(org_setup, manager_drf_client):
    """send_reminder returns 404 when no assignment exists for the supplied email."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(
        remind_url, data={"email": "nobody@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_send_reminder_forbidden(org_setup, manager_drf_client):
    """A manager cannot send reminders for codes in contracts they don't manage."""
    _, _, *_, (contract_3, *_) = org_setup

    discount = contract_3.get_discounts().order_by("id").first()

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_3.organization.id,
            "pk": contract_3.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(
        remind_url, data={"email": "assignee@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_send_reminder_already_redeemed(org_setup, manager_drf_client):
    """send_reminder returns 409 when the assignment has already been redeemed."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    user = UserFactory.create()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email=user.email,
        user=user,
    )

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(remind_url, format="json")

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "already claimed" in resp.json()["detail"]


def test_send_reminder_redeemed_on_set(org_setup, manager_drf_client):
    """send_reminder returns 409 when redeemed_on is set even without a linked user."""

    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="assignee@example.com",
        redeemed_on=now_in_utc(),
    )

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(remind_url, format="json")

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "already claimed" in resp.json()["detail"]


def test_send_reminder_no_assigned_email(org_setup, manager_drf_client):
    """send_reminder returns 409 when the assignment record has no assigned email."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="",
    )

    remind_url = reverse(
        "b2b:b2b-manager-org-contract-send-reminder-for-code-assignment",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.post(remind_url, format="json")

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "no assigned email" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# bulk_assign tests
# ---------------------------------------------------------------------------


def test_bulk_assign(org_setup, manager_drf_client, mocker):
    """A manager can bulk-assign codes, getting one code per submitted record."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )
    _, _, (contract_1, *_), *_ = org_setup

    records = [
        {"email": "learner1@example.com", "name": "Learner One"},
        {"email": "learner2@example.com", "name": "Learner Two"},
        {"email": "learner3@example.com", "name": "Learner Three"},
    ]

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    resp = manager_drf_client.post(bulk_assign_url, data=records, format="json")

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert len(resp_data["assigned"]) == 3
    assert len(resp_data["errors"]) == 0
    mock_task.delay.assert_called_once()

    assigned_emails = {code["assigned_to"] for code in resp_data["assigned"]}
    assert assigned_emails == {
        "learner1@example.com",
        "learner2@example.com",
        "learner3@example.com",
    }

    assert (
        DiscountContractAttachmentRedemption.objects.filter(
            contract=contract_1,
            assigned_email__in=[
                "learner1@example.com",
                "learner2@example.com",
                "learner3@example.com",
            ],
        ).count()
        == 3
    )


def test_bulk_assign_insufficient_codes(org_setup, manager_drf_client, mocker):
    """bulk_assign reports errors for records that exceed the number of available codes."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    # contract_1 has a real (non-zero) max_learners cap, so it never falls
    # into the on-the-fly provisioning codepath used for uncapped contracts.
    _, _, (contract_1, *_), *_ = org_setup

    available_count = (
        contract_1.get_discounts().filter(contract_redemptions__isnull=True).count()
    )

    # Request two more than are available so we get predictable errors.
    records = [{"email": f"learner{i}@example.com"} for i in range(available_count + 2)]

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    resp = manager_drf_client.post(bulk_assign_url, data=records, format="json")

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert len(resp_data["assigned"]) == available_count
    assert len(resp_data["errors"]) == 2
    assert all("No available code." in err["detail"] for err in resp_data["errors"])


def test_bulk_assign_provisions_codes_for_uncapped_contract(
    org_setup, manager_drf_client, mocker
):
    """bulk_assign provisions new one-time codes on the fly for contracts with no max_learners."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    _, _, (contract_1, *_), *_ = org_setup

    # Build a contract with no seat cap and a single product, in the same org
    # the manager already has access to, so we get an easy 1:1 relationship
    # between provisioned discounts and requested assignments.
    uncapped_contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=None,
        organization=contract_1.organization,
    )
    course_run = CourseRunFactory.create(b2b_contract=uncapped_contract)
    with reversion.create_revision():
        ProductFactory.create(purchasable_object=course_run)

    created, updated, errored = ensure_enrollment_codes_exist(uncapped_contract)
    assert created == 1
    assert updated == 0
    assert errored == 0

    # Only one code exists so far, but we're requesting three assignments.
    records = [
        {"email": "learner1@example.com", "name": "Learner One"},
        {"email": "learner2@example.com", "name": "Learner Two"},
        {"email": "learner3@example.com", "name": "Learner Three"},
    ]

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": uncapped_contract.organization.id,
            "pk": uncapped_contract.id,
        },
    )

    resp = manager_drf_client.post(bulk_assign_url, data=records, format="json")

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert len(resp_data["assigned"]) == 3
    assert len(resp_data["errors"]) == 0

    assigned_emails = {code["assigned_to"] for code in resp_data["assigned"]}
    assert assigned_emails == {
        "learner1@example.com",
        "learner2@example.com",
        "learner3@example.com",
    }

    # The pre-existing code plus two newly provisioned one-time codes should
    # cover all three assignments.
    contract_discounts = uncapped_contract.get_discounts()
    assert contract_discounts.count() == 3
    assert (
        contract_discounts.filter(redemption_type=REDEMPTION_TYPE_ONE_TIME).count() == 2
    )
    assert (
        DiscountContractAttachmentRedemption.objects.filter(
            contract=uncapped_contract
        ).count()
        == 3
    )


def test_bulk_assign_no_product_for_uncapped_contract(
    org_setup, manager_drf_client, mocker, caplog
):
    """bulk_assign doesnt attempt JIT code provisioning for a misconfigured contract without a product."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    _, _, (contract_1, *_), *_ = org_setup

    uncapped_contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=None,
        organization=contract_1.organization,
    )

    records = [
        {"email": "learner1@example.com", "name": "Learner One"},
        {"email": "learner2@example.com", "name": "Learner Two"},
    ]

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": uncapped_contract.organization.id,
            "pk": uncapped_contract.id,
        },
    )

    resp = manager_drf_client.post(bulk_assign_url, data=records, format="json")

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert len(resp_data["assigned"]) == 0
    assert len(resp_data["errors"]) == 2
    assert all("No available code." in err["detail"] for err in resp_data["errors"])

    assert uncapped_contract.get_discounts().count() == 0
    assert (
        DiscountContractAttachmentRedemption.objects.filter(
            contract=uncapped_contract
        ).count()
        == 0
    )
    assert "has no product" in caplog.text


def test_bulk_assign_skips_already_assigned_or_redeemed(
    org_setup, manager_drf_client, mocker
):
    """bulk_assign skips emails already assigned to or redeemed for the contract."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )
    _, _, (contract_1, *_), *_ = org_setup

    discounts = list(contract_1.get_discounts().order_by("id")[:2])

    # An email that has already been assigned a code.
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[0],
        contract=contract_1,
        assigned_email="assigned@example.com",
    )
    # An email belonging to a user who has redeemed a code.
    redeemer = UserFactory.create(email="redeemed@example.com")
    DiscountContractAttachmentRedemption.objects.create(
        discount=discounts[1],
        contract=contract_1,
        user=redeemer,
    )

    records = [
        {"email": "assigned@example.com", "name": "Already Assigned"},
        {"email": "REDEEMED@example.com", "name": "Already Redeemed"},
        {"email": "fresh@example.com", "name": "Fresh Learner"},
    ]

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    resp = manager_drf_client.post(bulk_assign_url, data=records, format="json")

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert len(resp_data["assigned"]) == 1
    assert resp_data["assigned"][0]["assigned_to"] == "fresh@example.com"

    error_emails = {err["email"] for err in resp_data["errors"]}
    assert error_emails == {"assigned@example.com", "REDEEMED@example.com"}
    assert all(
        "already been assigned or has redeemed" in err["detail"]
        for err in resp_data["errors"]
    )

    # Only the fresh learner triggers an invite email.
    mock_task.delay.assert_called_once()
    assert (
        not DiscountContractAttachmentRedemption.objects.filter(
            contract=contract_1, assigned_email="assigned@example.com"
        )
        .exclude(discount=discounts[0])
        .exists()
    )


def test_bulk_assign_deduplicates_emails(org_setup, manager_drf_client, mocker):
    """bulk_assign keeps only the first record for each duplicated email."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )
    _, _, (contract_1, *_), *_ = org_setup

    records = [
        {"email": "dup@example.com", "name": "First"},
        {"email": "DUP@example.com", "name": "Second"},
        {"email": "other@example.com", "name": "Other"},
    ]

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    resp = manager_drf_client.post(bulk_assign_url, data=records, format="json")

    assert resp.status_code == status.HTTP_200_OK

    resp_data = resp.json()
    assert len(resp_data["assigned"]) == 2
    assert len(resp_data["errors"]) == 0
    mock_task.delay.assert_called_once()

    assigned = DiscountContractAttachmentRedemption.objects.filter(
        contract=contract_1, assigned_email="dup@example.com"
    )
    assert assigned.count() == 1
    assert assigned.first().assigned_name == "First"


def test_bulk_assign_invalid_request(org_setup, manager_drf_client):
    """bulk_assign returns 400 when the request body is not a list."""
    _, _, (contract_1, *_), *_ = org_setup

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    # Send a dict instead of a list — should fail ListSerializer validation.
    resp = manager_drf_client.post(
        bulk_assign_url,
        data={"email": "notalist@example.com"},
        format="json",
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_bulk_assign_forbidden(org_setup, manager_drf_client):
    """A manager cannot bulk-assign codes for a contract they don't manage."""
    _, _, *_, (contract_3, *_) = org_setup

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_3.organization.id,
            "pk": contract_3.id,
        },
    )

    resp = manager_drf_client.post(
        bulk_assign_url,
        data=[{"email": "learner@example.com"}],
        format="json",
    )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_bulk_assign_internal_error(org_setup, manager_drf_client, mocker):
    """bulk_assign returns 500 when the assignment DB operation fails."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    mocker.patch(
        "b2b.views.v0.manager.assign_codes_and_send_emails", return_value=False
    )
    _, _, (contract_1, *_), *_ = org_setup

    bulk_assign_url = reverse(
        "b2b:b2b-manager-org-contract-bulk-assign",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
        },
    )

    resp = manager_drf_client.post(
        bulk_assign_url,
        data=[{"email": "learner@example.com"}],
        format="json",
    )

    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# reassign_code tests
# ---------------------------------------------------------------------------


def test_reassign_code(org_setup, manager_drf_client, mocker):
    """A manager can reassign an assigned code to a new email address."""
    mock_task = mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    original_code = discount.discount_code
    redemption = DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="original@example.com",
        assigned_name="Original Name",
    )

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.put(
        reassign_url,
        data={"email": "new@example.com", "name": "New Name"},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK

    redemption.refresh_from_db()
    assert redemption.assigned_email == "new@example.com"
    mock_task.delay.assert_called_once_with([redemption.id])

    resp_data = resp.json()
    assert resp_data["code"] != original_code
    assert resp_data["redemption_status"] == REDEMPTION_STATUS_ASSIGNED
    assert resp_data["assigned_to"] == "new@example.com"


def test_reassign_code_updates_assigned_by(org_setup, manager_drf_client, mocker):
    """reassign_code stamps the requesting manager as assigned_by."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    manager_user, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    redemption = DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="original@example.com",
    )

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    manager_drf_client.put(
        reassign_url,
        data={"email": "new@example.com"},
        format="json",
    )

    redemption.refresh_from_db()
    assert redemption.assigned_by == manager_user


def test_reassign_code_name_defaults_to_empty(org_setup, manager_drf_client, mocker):
    """Reassigning a code without a name stores an empty string for assigned_name."""
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="original@example.com",
        assigned_name="Old Name",
    )

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.put(
        reassign_url,
        data={"email": "new@example.com"},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["assigned_name"] == ""


def test_reassign_code_invalid_request(org_setup, manager_drf_client):
    """reassign_code returns 400 when the request body is missing the required email field."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="original@example.com",
    )

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.put(
        reassign_url, data={"name": "No Email"}, format="json"
    )

    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_reassign_code_not_found(org_setup, manager_drf_client):
    """reassign_code returns 404 when the code does not belong to the contract."""
    _, _, (contract_1, *_), *_ = org_setup

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": "nonexistent-code",
        },
    )

    resp = manager_drf_client.put(
        reassign_url, data={"email": "new@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "detail" in resp.json()


def test_reassign_code_no_assignment(org_setup, manager_drf_client):
    """reassign_code returns 404 when no assignment exists for the code."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.put(
        reassign_url, data={"email": "new@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "detail" in resp.json()


def test_reassign_code_already_redeemed(org_setup, manager_drf_client):
    """reassign_code returns 409 when the code has already been redeemed by a user."""
    _, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    redeemer = UserFactory.create()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_1,
        assigned_email="assignee@example.com",
        user=redeemer,
    )

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_1.organization.id,
            "pk": contract_1.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.put(
        reassign_url, data={"email": "new@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "detail" in resp.json()


def test_reassign_code_forbidden(org_setup, manager_drf_client):
    """A manager cannot reassign codes for a contract belonging to an org they don't manage."""
    _, _, *_, (contract_3, *_) = org_setup

    discount = contract_3.get_discounts().order_by("id").first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=discount,
        contract=contract_3,
        assigned_email="original@example.com",
    )

    reassign_url = reverse(
        "b2b:b2b-manager-org-contract-reassign-code",
        kwargs={
            "parent_lookup_organization": contract_3.organization.id,
            "pk": contract_3.id,
            "code": discount.discount_code,
        },
    )

    resp = manager_drf_client.put(
        reassign_url, data={"email": "new@example.com"}, format="json"
    )

    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_manager_org_list_unauthenticated():
    """Unauthenticated requests to the org list are rejected (403 — DRF session auth)."""
    client = APIClient()
    url = reverse("b2b:b2b-manager-organization-list")
    resp = client.get(url)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_manager_org_retrieve_unauthenticated(org_setup):
    """Unauthenticated requests to the org detail are rejected (403 — DRF session auth)."""
    _, orgs, *_ = org_setup
    client = APIClient()
    url = reverse("b2b:b2b-manager-organization-detail", kwargs={"pk": orgs[0].id})
    resp = client.get(url)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_manager_org_list_non_manager_sees_empty():
    """An authenticated user with no manager memberships sees an empty list."""
    non_manager = UserFactory.create()
    client = APIClient()
    client.force_login(non_manager)
    url = reverse("b2b:b2b-manager-organization-list")
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["results"] == []


def test_manager_org_list_member_not_manager_sees_empty(org_setup):
    """A user who is a member of an org but not a manager sees an empty list."""
    _, orgs, *_ = org_setup
    member = UserFactory.create()
    UserOrganization.objects.create(
        user=member,
        organization=orgs[0],
        keep_until_seen=True,
        is_manager=False,
    )
    client = APIClient()
    client.force_login(member)
    url = reverse("b2b:b2b-manager-organization-list")
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["results"] == []


def test_manager_org_retrieve_success(org_setup, manager_drf_client):
    """A manager can retrieve their organization by ID."""
    _, orgs, *_ = org_setup
    url = reverse("b2b:b2b-manager-organization-detail", kwargs={"pk": orgs[0].id})
    resp = manager_drf_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == orgs[0].id
    assert "name" in data
    assert "slug" in data
    assert "contracts" in data


def test_manager_org_retrieve_not_managed_returns_404(org_setup, manager_drf_client):
    """A manager cannot retrieve an org they don't manage — filtered out as 404."""
    _, orgs, *_ = org_setup
    url = reverse("b2b:b2b-manager-organization-detail", kwargs={"pk": orgs[1].id})
    resp = manager_drf_client.get(url)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_manager_org_retrieve_nonexistent_returns_404(manager_drf_client):
    """Retrieving a non-existent org ID returns 404."""
    url = reverse("b2b:b2b-manager-organization-detail", kwargs={"pk": 999999})
    resp = manager_drf_client.get(url)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_manager_org_list_only_active_contracts(org_setup, manager_drf_client):
    """Inactive contracts are excluded from the org list response."""
    _, _orgs, (contract_1, *_), *_ = org_setup
    contract_1.active = False
    contract_1.save()

    url = reverse("b2b:b2b-manager-organization-list")
    resp = manager_drf_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    org_data = resp.json()["results"][0]
    contract_ids = [c["id"] for c in org_data["contracts"]]
    assert contract_1.id not in contract_ids


def test_manager_org_retrieve_only_active_contracts(org_setup, manager_drf_client):
    """Inactive contracts are excluded from the org retrieve response."""
    _, orgs, (contract_1, *_), (contract_2, *_), *_ = org_setup
    contract_1.active = False
    contract_1.save()

    url = reverse("b2b:b2b-manager-organization-detail", kwargs={"pk": orgs[0].id})
    resp = manager_drf_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    contract_ids = [c["id"] for c in resp.json()["contracts"]]
    assert contract_1.id not in contract_ids
    assert contract_2.id in contract_ids


def test_manager_org_list_multiple_managed_orgs():
    """A manager attached to multiple orgs sees all of them."""
    manager = UserFactory.create()
    org_1 = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE
    ).organization
    org_2 = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE
    ).organization
    UserOrganization.objects.create(
        user=manager, organization=org_1, keep_until_seen=True, is_manager=True
    )
    UserOrganization.objects.create(
        user=manager, organization=org_2, keep_until_seen=True, is_manager=True
    )
    client = APIClient()
    client.force_login(manager)
    url = reverse("b2b:b2b-manager-organization-list")
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    result_ids = {r["id"] for r in resp.json()["results"]}
    assert org_1.id in result_ids
    assert org_2.id in result_ids


# ---------------------------------------------------------------------------
# assign_codes_and_send_emails unit tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_email_task(mocker):
    return mocker.patch(
        "b2b.views.v0.manager.queue_send_enrollment_code_assignment_email"
    )


def test_assign_codes_and_send_emails_creates_records(org_setup, mock_email_task):
    """Happy path: DB records are created and the email task is queued."""
    manager_user, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    assignment = CodeAssignment(
        contract=contract_1,
        discount=discount,
        email="learner@example.com",
        name="Test Learner",
        code=discount.discount_code,
    )

    result = assign_codes_and_send_emails([assignment], manager_user)

    assert result is True
    record = DiscountContractAttachmentRedemption.objects.get(
        discount=discount, assigned_email="learner@example.com"
    )
    assert record.assigned_name == "Test Learner"
    assert record.assigned_by == manager_user
    assert record.contract == contract_1


def test_assign_codes_and_send_emails_queues_email_with_record_ids(
    org_setup, mock_email_task
):
    """The email task is called with the IDs of the newly created records."""
    manager_user, _, (contract_1, *_), *_ = org_setup

    discounts = list(contract_1.get_discounts().order_by("id")[:2])
    assignments = [
        CodeAssignment(
            contract=contract_1,
            discount=d,
            email=f"learner{i}@example.com",
            name=f"Learner {i}",
            code=d.discount_code,
        )
        for i, d in enumerate(discounts)
    ]

    assign_codes_and_send_emails(assignments, manager_user)

    created_ids = list(
        DiscountContractAttachmentRedemption.objects.filter(
            contract=contract_1,
            assigned_email__in=["learner0@example.com", "learner1@example.com"],
        ).values_list("id", flat=True)
    )
    mock_email_task.delay.assert_called_once_with(created_ids)


def test_assign_codes_and_send_emails_sets_prefetched_redemptions(
    org_setup, mock_email_task
):
    """discount.prefetched_redemptions is populated so serializers skip the DB query."""
    manager_user, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    assignment = CodeAssignment(
        contract=contract_1,
        discount=discount,
        email="learner@example.com",
        name="Test Learner",
        code=discount.discount_code,
    )

    assign_codes_and_send_emails([assignment], manager_user)

    assert hasattr(discount, "prefetched_redemptions")
    assert len(discount.prefetched_redemptions) == 1
    assert discount.prefetched_redemptions[0].assigned_email == "learner@example.com"


def test_assign_codes_and_send_emails_bulk_create_failure(
    org_setup, mock_email_task, mocker
):
    """assign_codes_and_send_emails returns False and skips email when bulk_create raises."""
    manager_user, _, (contract_1, *_), *_ = org_setup
    discount = contract_1.get_discounts().order_by("id").first()
    assignment = CodeAssignment(
        contract=contract_1,
        discount=discount,
        email="learner@example.com",
        name="Test Learner",
        code=discount.discount_code,
    )

    mocker.patch.object(
        DiscountContractAttachmentRedemption.objects,
        "bulk_create",
        side_effect=Exception("DB error"),
    )

    result = assign_codes_and_send_emails([assignment], manager_user)

    assert result is False
    mock_email_task.delay.assert_not_called()

    assert result is False
    mock_email_task.delay.assert_not_called()
    assert not DiscountContractAttachmentRedemption.objects.filter(
        discount=discount, assigned_email="learner@example.com"
    ).exists()


def test_assign_codes_and_send_emails_empty_list(org_setup, mock_email_task):
    """An empty assignments list creates no records and dispatches no task."""
    manager_user, *_ = org_setup

    result = assign_codes_and_send_emails([], manager_user)

    assert result is True
    assert not DiscountContractAttachmentRedemption.objects.exists()
    mock_email_task.delay.assert_not_called()


def test_assign_codes_and_send_emails_timestamps_are_set(org_setup, mock_email_task):
    """created_on, updated_on, and last_reminder_sent_on are populated."""
    manager_user, _, (contract_1, *_), *_ = org_setup

    discount = contract_1.get_discounts().order_by("id").first()
    assignment = CodeAssignment(
        contract=contract_1,
        discount=discount,
        email="learner@example.com",
        name="Test Learner",
        code=discount.discount_code,
    )

    assign_codes_and_send_emails([assignment], manager_user)

    record = DiscountContractAttachmentRedemption.objects.get(
        discount=discount, assigned_email="learner@example.com"
    )
    assert record.created_on is not None
    assert record.updated_on is not None
    assert record.last_reminder_sent_on is not None
