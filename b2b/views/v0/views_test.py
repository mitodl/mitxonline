"""
Tests for B2B views.
"""

from datetime import timedelta

import pytest
import reversion
from django.urls import reverse
from freezegun import freeze_time
from mitol.common.utils.datetime import now_in_utc
from rest_framework.test import APIClient

from b2b.api import create_contract_run, ensure_enrollment_codes_exist
from b2b.constants import (
    CONTRACT_MEMBERSHIP_CODE,
    CONTRACT_MEMBERSHIP_MANAGED,
)
from b2b.factories import ContractPageFactory
from b2b.models import DiscountContractAttachmentRedemption, UserOrganization
from courses.factories import CourseRunFactory
from courses.models import CourseRunEnrollment
from ecommerce.factories import ProductFactory, UnlimitedUseDiscountFactory
from main.constants import (
    USER_MSG_TYPE_B2B_ENROLL_SUCCESS,
    USER_MSG_TYPE_B2B_ERROR_ALREADY_ENROLLED,
    USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT,
    USER_MSG_TYPE_B2B_ERROR_NOT_ENROLLABLE,
    USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


def test_b2b_contract_attachment_bad_code(user):
    """Ensure a bad code passed in won't work."""
    client = APIClient()
    client.force_login(user)
    assert user.b2b_contracts.count() == 0

    url = reverse("b2b:attach-user", kwargs={"enrollment_code": "not a code"})
    resp = client.post(url)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Invalid or expired enrollment code."
    assert user.b2b_contracts.count() == 0


def test_b2b_contract_attachment_code_with_no_contracts(user):
    """Ensure a code not tied to any B2B contracts returns 404."""
    client = APIClient()
    client.force_login(user)

    discount = UnlimitedUseDiscountFactory.create()

    url = reverse("b2b:attach-user", kwargs={"enrollment_code": discount.discount_code})
    resp = client.post(url)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "No contracts found for this code."
    assert user.b2b_contracts.count() == 0


@pytest.mark.parametrize(
    "max_learners",
    [
        10,
        None,
    ],
)
@pytest.mark.parametrize(
    "code_used",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "contract_active",
    [
        "active",
        "date",
        "flag",
    ],
)
def test_b2b_contract_attachment(mocker, max_learners, code_used, contract_active):
    """Ensure a supplied code results in attachment for the user."""

    mocked_attach_user = mocker.patch(
        "b2b.models.OrganizationPage.attach_user", return_value=True
    )

    user = UserFactory.create()

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=max_learners,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_codes = contract.get_discounts().all()

    if code_used:
        other_user = UserFactory.create()
        DiscountContractAttachmentRedemption.objects.create(
            discount=contract_codes[0],
            user=other_user,
            contract=contract,
        )

    if contract_active == "date":
        contract.contract_start = now_in_utc() + timedelta(days=30)
        contract.save()

    if contract_active == "flag":
        contract.active = False
        contract.save()

    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_codes[0].discount_code}
    )
    resp = client.post(url)

    user.refresh_from_db()

    if (code_used and max_learners) or contract_active in ["flag", "date"]:
        # Code already used for attachment and is not unlimited - should return 404
        assert resp.status_code == 404
        assert resp.json()["detail"] in [
            "No contracts found for this code.",
            "Invalid or expired enrollment code.",
        ]
        assert not user.b2b_organizations.filter(pk=contract.organization.id).exists()
        assert not user.b2b_contracts.filter(pk=contract.id).exists()

        assert not DiscountContractAttachmentRedemption.objects.filter(
            contract=contract, user=user, discount=contract_codes[0]
        ).exists()
    else:
        # Successfully attached to contract - should return 201
        assert resp.status_code == 201
        mocked_attach_user.assert_called()

        assert user.b2b_organizations.filter(pk=contract.organization.id).exists()
        assert user.b2b_contracts.filter(pk=contract.id).exists()

        assert DiscountContractAttachmentRedemption.objects.filter(
            contract=contract, user=user, discount=contract_codes[0]
        ).exists()
        assert resp.json()[0]["id"] == contract.id


def test_b2b_contract_attachment_response_excludes_unrelated_contracts(mocker):
    """The attach response should only include contracts tied to the redeemed code."""

    mocker.patch("b2b.models.OrganizationPage.attach_user", return_value=True)

    user = UserFactory.create()
    unrelated_contract = ContractPageFactory.create()
    user.b2b_contracts.add(unrelated_contract)

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    assert resp.status_code == 201
    assert resp.json()[0]["id"] == contract.id


def test_b2b_contract_attachment_returns_matching_contract_when_already_attached(
    mocker,
):
    """A valid code should return its matching contract even if already attached."""

    mocked_attach_user = mocker.patch(
        "b2b.models.OrganizationPage.attach_user", return_value=True
    )

    user = UserFactory.create()
    unrelated_contract = ContractPageFactory.create()
    user.b2b_contracts.add(unrelated_contract)

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    user.b2b_contracts.add(contract)

    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    assert resp.status_code == 200
    assert resp.json()[0]["id"] == contract.id
    mocked_attach_user.assert_not_called()


@pytest.mark.parametrize(
    "bad_start_or_end",
    [
        True,
        False,
    ],
)
def test_b2b_contract_attachment_invalid_code_dates(user, bad_start_or_end):
    """Test that the attachment fails properly if the code has invalid dates."""

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=1,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    # Normally, the codes follow the start/end dates on the contract.
    # But we can change that and it's supposed to check both the contract and the
    # discount code.

    if bad_start_or_end:
        contract_code.activation_date = now_in_utc() + timedelta(days=2)
    else:
        contract_code.expiration_date = now_in_utc() + timedelta(hours=1)

    contract_code.save()
    contract_code.refresh_from_db()

    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    slightly_future_time = now_in_utc() + timedelta(hours=3)

    with freeze_time(slightly_future_time):
        resp = client.post(url)

    # Code is expired/not yet active - should return 404
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Invalid or expired enrollment code."

    user.refresh_from_db()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()
    assert not DiscountContractAttachmentRedemption.objects.filter(
        contract=contract, user=user, discount=contract_code
    ).exists()


@pytest.mark.parametrize(
    "bad_start_or_end",
    [
        True,
        False,
    ],
)
def test_b2b_contract_attachment_invalid_contract_dates(user, bad_start_or_end):
    """Test that the attachment fails properly if the contract has invalid dates."""

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=1,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    # As in invalid_code_dates, usually the codes will get created with the start
    # and/or end dates of the contract. This changes the contract so we can
    # test just the contract date logic.

    if bad_start_or_end:
        contract.contract_start = now_in_utc() + timedelta(days=3)
    else:
        contract.contract_end = now_in_utc() + timedelta(days=1)

    contract.save()
    contract.refresh_from_db()

    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    slightly_future_time = now_in_utc() + timedelta(days=2)

    with freeze_time(slightly_future_time):
        resp = client.post(url)

    # Contract dates are invalid - code is valid but no contracts to attach - should return 404
    assert resp.status_code == 404
    assert "detail" in resp.json()

    user.refresh_from_db()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()
    assert not DiscountContractAttachmentRedemption.objects.filter(
        contract=contract, user=user, discount=contract_code
    ).exists()


def test_b2b_contract_attachment_full_contract(mocker):
    """Test that the attachment fails properly if the contract is full."""

    mocked_attach_user = mocker.patch(
        "b2b.models.OrganizationPage.attach_user", return_value=True
    )

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=1,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    # Fill the contract to capacity with another user
    existing_user = UserFactory.create()
    existing_user.b2b_contracts.add(contract)
    existing_user.save()

    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    # Contract is full - should return an error and not attach user
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Contract is full."
    mocked_attach_user.assert_not_called()

    user.refresh_from_db()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()

    user.refresh_from_db()
    assert not user.b2b_organizations.filter(pk=contract.organization.id).exists()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()
    assert not DiscountContractAttachmentRedemption.objects.filter(
        contract=contract, user=user, discount=contract_code
    ).exists()


def test_b2b_contract_attachment_full_contract_with_used_code(mocker):
    """If the contract is full and the code was already used, return 409."""

    mocked_attach_user = mocker.patch(
        "b2b.models.OrganizationPage.attach_user", return_value=True
    )

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=1,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    # Fill the contract and mark the code as used by another user
    existing_user = UserFactory.create()
    existing_user.b2b_contracts.add(contract)
    existing_user.save()

    DiscountContractAttachmentRedemption.objects.create(
        discount=contract_code,
        user=existing_user,
        contract=contract,
    )

    # New user attempts to attach with the same code
    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    # Contract is full - should return 409 and not attach user
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Contract is full."
    mocked_attach_user.assert_not_called()

    user.refresh_from_db()
    assert not user.b2b_organizations.filter(pk=contract.organization.id).exists()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()
    assert not DiscountContractAttachmentRedemption.objects.filter(
        contract=contract, user=user, discount=contract_code
    ).exists()


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize("user_has_edx_user", [True, False])
@pytest.mark.parametrize("has_price", [True, False])
@pytest.mark.parametrize("run_is_enrollable", [True, False])
@pytest.mark.parametrize(
    "contract_active",
    [
        "active",
        "date",
        "flag",
    ],
)
def test_b2b_enroll(  # noqa: PLR0915, PLR0913
    mocker, settings, user_has_edx_user, has_price, run_is_enrollable, contract_active
):
    """Make sure that hitting the enroll endpoint actually results in enrollments"""

    mocker.patch("hubspot_sync.tasks.sync_cart_add_event_with_hubspot.apply_async")
    mocked_create_from_id = mocker.patch("openedx.tasks.create_user_from_id")
    mocker.patch("openedx.tasks.clone_courserun.delay")
    mocked_create_user_request = mocker.patch("openedx.api._create_edx_user_request")
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "a token"  # noqa: S105

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
        enrollment_fixed_price=100 if has_price else 0,
    )
    source_courserun = CourseRunFactory.create(
        is_source_run=True, language="en", is_primary_language=True
    )

    [
        (courserun, _),
    ] = create_contract_run(contract, source_courserun.course, queue_codes=True)

    if not run_is_enrollable:
        courserun.live = False
        courserun.save()

    user = UserFactory.create(no_openedx_user=(not user_has_edx_user))

    if user_has_edx_user:
        assert user.openedx_user
    else:
        assert not user.openedx_user

    user.b2b_contracts.add(contract)
    user.save()
    user.refresh_from_db()

    if user_has_edx_user:
        assert user.openedx_user
    else:
        assert not user.openedx_user

    if contract_active == "date":
        contract.contract_start = now_in_utc() + timedelta(days=30)
        contract.save()

    if contract_active == "flag":
        contract.active = False
        contract.save()

    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    resp = client.post(url)

    if not run_is_enrollable:
        assert resp.status_code == 400
        assert resp.json()["result"] == USER_MSG_TYPE_B2B_ERROR_NOT_ENROLLABLE
        return

    if contract_active in ["date", "flag"]:
        assert resp.status_code == 400
        assert resp.json()["result"] == USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT
        return

    if has_price:
        assert resp.status_code == 400
        assert resp.json()["result"] == USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT
        return

    assert resp.status_code == 201
    assert resp.json()["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS

    user.refresh_from_db()

    if not user_has_edx_user:
        mocked_create_user_request.assert_called()
        mocked_create_from_id.assert_not_called()

    del user.openedx_user
    assert user.edx_username
    assert CourseRunEnrollment.objects.filter(user=user, run=courserun).exists()


def test_preassigned_code_can_be_redeemed(mocker):
    """
    A code pre-assigned by a manager should be redeemable by the intended learner.
    """
    mocker.patch("b2b.models.OrganizationPage.attach_user", return_value=True)
    mocker.patch("b2b.views.v0.manager.queue_send_enrollment_code_assignment_email")

    manager = UserFactory.create()
    learner = UserFactory.create()

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=20,
    )
    UserOrganization.objects.create(
        user=manager,
        organization=contract.organization,
        keep_until_seen=True,
        is_manager=True,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    with reversion.create_revision():
        ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    discount = contract.get_discounts().order_by("id").first()
    code = discount.discount_code

    # Manager pre-assigns the code to the learner's email address.
    manager_client = APIClient()
    manager_client.force_login(manager)
    assign_url = reverse(
        "b2b:b2b-manager-org-contract-assign-code",
        kwargs={
            "parent_lookup_organization": contract.organization.id,
            "pk": contract.id,
            "code": code,
        },
    )
    assign_resp = manager_client.post(
        assign_url,
        data={"email": learner.email, "name": "Test Learner"},
        format="json",
    )
    assert assign_resp.status_code == 200

    # The pre-assignment record exists but is not yet redeemed.
    assert DiscountContractAttachmentRedemption.objects.filter(
        discount=discount,
        assigned_email=learner.email,
        redeemed_on__isnull=True,
        user__isnull=True,
    ).exists()

    # Learner redeems the assigned code — should succeed with 201.
    learner_client = APIClient()
    learner_client.force_login(learner)
    attach_url = reverse("b2b:attach-user", kwargs={"enrollment_code": code})
    redeem_resp = learner_client.post(attach_url)

    assert redeem_resp.status_code == 201
    learner.refresh_from_db()
    assert learner.b2b_contracts.filter(pk=contract.id).exists()

    # Exactly one record should exist — the pre-assignment row updated in place,
    # not a second record created alongside it.
    records = DiscountContractAttachmentRedemption.objects.filter(
        discount=discount, contract=contract
    )
    assert records.count() == 1
    record = records.get()
    assert record.user == learner
    assert record.redeemed_on is not None
    assert record.assigned_email == learner.email


def test_enroll_requires_authentication():
    """Unauthenticated requests to the enroll endpoint should return 401."""
    client = APIClient()
    url = reverse("b2b:enroll-user", kwargs={"readable_id": "course-v1:MITx+Test+2024"})
    resp = client.post(url)
    assert resp.status_code == 401


def test_enroll_courserun_not_found(mocker):
    """A readable_id with no matching B2B course run should raise a 500 (DoesNotExist propagates)."""
    mocker.patch("b2b.views.v0.create_b2b_enrollment")
    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:enroll-user", kwargs={"readable_id": "course-v1:MITx+DoesNotExist+2024"}
    )
    with pytest.raises(Exception):  # noqa: B017, PT011
        client.post(url)


def test_enroll_product_not_found(mocker):
    """A course run with no associated product should raise DoesNotExist."""
    mocker.patch("b2b.views.v0.create_b2b_enrollment")
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
        enrollment_fixed_price=0,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    # Intentionally do not create a Product for courserun

    user = UserFactory.create()
    user.b2b_contracts.add(contract)
    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    with pytest.raises(Exception):  # noqa: B017, PT011
        client.post(url)


def test_enroll_success(mocker):
    """A valid request with a free B2B course run returns 201 on success."""
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
        enrollment_fixed_price=0,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    mocker.patch(
        "b2b.views.v0.create_b2b_enrollment",
        return_value={"result": USER_MSG_TYPE_B2B_ENROLL_SUCCESS},
    )

    user = UserFactory.create()
    user.b2b_contracts.add(contract)
    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    resp = client.post(url)

    assert resp.status_code == 201
    assert resp.json()["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS


@pytest.mark.parametrize(
    "error_result",
    [
        USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT,
        USER_MSG_TYPE_B2B_ERROR_NOT_ENROLLABLE,
        USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT,
        USER_MSG_TYPE_B2B_ERROR_ALREADY_ENROLLED,
    ],
)
def test_enroll_failure_returns_400(mocker, error_result):
    """Any non-success result from create_b2b_enrollment should return 400."""
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
        enrollment_fixed_price=0,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    mocker.patch(
        "b2b.views.v0.create_b2b_enrollment",
        return_value={"result": error_result},
    )

    user = UserFactory.create()
    user.b2b_contracts.add(contract)
    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    resp = client.post(url)

    assert resp.status_code == 400
    assert resp.json()["result"] == error_result


def test_enroll_passes_program_id_to_api(mocker):
    """The program_id from the request body should be forwarded to create_b2b_enrollment."""
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
        enrollment_fixed_price=0,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    mocked_enroll = mocker.patch(
        "b2b.views.v0.create_b2b_enrollment",
        return_value={"result": USER_MSG_TYPE_B2B_ENROLL_SUCCESS},
    )

    user = UserFactory.create()
    user.b2b_contracts.add(contract)
    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    resp = client.post(url, data={"program_id": "program-v1:MITx+TestProg"}, format="json")

    assert resp.status_code == 201
    _, kwargs = mocked_enroll.call_args
    assert kwargs["program_id"] == "program-v1:MITx+TestProg"


def test_enroll_omits_program_id_when_not_provided(mocker):
    """When program_id is absent from the request, it should be passed as None."""
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED,
        enrollment_fixed_price=0,
    )
    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    mocked_enroll = mocker.patch(
        "b2b.views.v0.create_b2b_enrollment",
        return_value={"result": USER_MSG_TYPE_B2B_ENROLL_SUCCESS},
    )

    user = UserFactory.create()
    user.b2b_contracts.add(contract)
    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    resp = client.post(url)

    assert resp.status_code == 201
    _, kwargs = mocked_enroll.call_args
    assert kwargs["program_id"] is None


def test_enroll_courserun_without_b2b_contract_not_found(mocker):
    """A course run that exists but has no b2b_contract should not be matched."""
    mocker.patch("b2b.views.v0.create_b2b_enrollment")
    courserun = CourseRunFactory.create(b2b_contract=None)
    ProductFactory.create(purchasable_object=courserun)

    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    with pytest.raises(Exception):  # noqa: B017, PT011
        client.post(url)
