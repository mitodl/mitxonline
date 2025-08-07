"""
Tests for B2B views.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time
from mitol.common.utils.datetime import now_in_utc
from rest_framework.test import APIClient

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_INTEGRATION_NONSSO
from b2b.factories import ContractPageFactory
from b2b.models import DiscountContractAttachmentRedemption
from courses.factories import CourseRunFactory
from ecommerce.factories import ProductFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("raise_nplusone")]


def test_b2b_contract_attachment_bad_code(user):
    """Ensure a bad code passed in won't work."""
    client = APIClient()
    client.force_login(user)
    assert user.b2b_contracts.count() == 0

    url = reverse("b2b:attach-user", kwargs={"enrollment_code": "not a code"})
    resp = client.post(url)

    assert resp.status_code == 200
    assert user.b2b_contracts.count() == 0


def test_b2b_contract_attachment(user):
    """Ensure a supplied code results in attachment for the user."""

    contract = ContractPageFactory.create(
        integration_type=CONTRACT_INTEGRATION_NONSSO,
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

    user.refresh_from_db()
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
        integration_type=CONTRACT_INTEGRATION_NONSSO,
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
        integration_type=CONTRACT_INTEGRATION_NONSSO,
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


def test_b2b_contract_attachment_full_contract():
    """Test that the attachment fails properly if the contract is full."""

    contract = ContractPageFactory.create(
        integration_type=CONTRACT_INTEGRATION_NONSSO,
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

    user.refresh_from_db()
    assert user.b2b_contracts.filter(pk=contract.id).exists()

    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    url = reverse(
        "b2b:attach-user", kwargs={"enrollment_code": contract_code.discount_code}
    )
    resp = client.post(url)

    assert resp.status_code == 200

    user.refresh_from_db()
    assert not user.b2b_contracts.filter(pk=contract.id).exists()
