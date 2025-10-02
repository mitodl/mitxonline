"""
Tests for B2B views.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time
from mitol.common.utils.datetime import now_in_utc
from rest_framework.test import APIClient

from b2b.api import create_contract_run, ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_MEMBERSHIP_NONSSO, CONTRACT_MEMBERSHIP_SSO
from b2b.factories import ContractPageFactory
from b2b.models import DiscountContractAttachmentRedemption
from courses.factories import CourseRunFactory
from courses.models import CourseRunEnrollment
from ecommerce.factories import ProductFactory
from main.constants import (
    USER_MSG_TYPE_B2B_ENROLL_SUCCESS,
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

    assert resp.status_code == 200
    assert user.b2b_contracts.count() == 0


def test_b2b_contract_attachment(mocker, user):
    """Ensure a supplied code results in attachment for the user."""

    mocked_attach_user = mocker.patch(
        "b2b.models.OrganizationPage.attach_user", return_value=True
    )

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_NONSSO,
        max_learners=10,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_codes = contract.get_discounts().all()

    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_codes[0].discount_code}
    )
    resp = client.post(url)

    assert resp.status_code == 200
    mocked_attach_user.assert_called()

    user.refresh_from_db()
    assert user.b2b_organizations.filter(organization=contract.organization).exists()
    assert user.b2b_contracts.filter(pk=contract.id).exists()

    assert DiscountContractAttachmentRedemption.objects.filter(
        contract=contract, user=user, discount=contract_codes[0]
    ).exists()


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
        membership_type=CONTRACT_MEMBERSHIP_NONSSO,
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

    assert resp.status_code == 200

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
        membership_type=CONTRACT_MEMBERSHIP_NONSSO,
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

    assert resp.status_code == 200

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
        membership_type=CONTRACT_MEMBERSHIP_NONSSO,
        max_learners=1,
    )

    courserun = CourseRunFactory.create(b2b_contract=contract)
    ProductFactory.create(purchasable_object=courserun)

    ensure_enrollment_codes_exist(contract)
    contract_code = contract.get_discounts().first()

    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    assert resp.status_code == 200
    mocked_attach_user.assert_called()

    user.refresh_from_db()
    assert user.b2b_contracts.filter(pk=contract.id).exists()

    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    mocked_attach_user.reset_mock()

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    assert resp.status_code == 200
    mocked_attach_user.assert_not_called()

    user.refresh_from_db()
    assert not user.b2b_organizations.filter(
        organization=contract.organization
    ).exists()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()
    assert not DiscountContractAttachmentRedemption.objects.filter(
        contract=contract, user=user, discount=contract_code
    ).exists()


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize("user_has_edx_user", [True, False])
@pytest.mark.parametrize("has_price", [True, False])
def test_b2b_enroll(mocker, settings, user_has_edx_user, has_price):
    """Make sure that hitting the enroll endpoint actually results in enrollments"""

    mocker.patch("openedx.tasks.clone_courserun.delay")
    mocker.patch("openedx.api._create_edx_user_request")
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "a token"  # noqa: S105

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_SSO,
        enrollment_fixed_price=100 if has_price else 0,
    )
    source_courserun = CourseRunFactory.create(is_source_run=True)

    courserun, _ = create_contract_run(contract, source_courserun.course)

    user = UserFactory.create()
    user.b2b_contracts.add(contract)

    if not user_has_edx_user:
        user.openedx_users.all().delete()

    user.save()
    user.refresh_from_db()

    client = APIClient()
    client.force_login(user)

    url = reverse("b2b:enroll-user", kwargs={"readable_id": courserun.courseware_id})
    resp = client.post(url)

    if has_price:
        assert resp.status_code == 406
        assert resp.json()["result"] == USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT
    else:
        assert resp.status_code == 201
        assert resp.json()["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS

        user.refresh_from_db()

        assert user.edx_username
        assert CourseRunEnrollment.objects.filter(user=user, run=courserun).exists()
