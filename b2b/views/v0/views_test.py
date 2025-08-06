"""
Tests for B2B views.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import CONTRACT_INTEGRATION_NONSSO
from b2b.factories import ContractPageFactory
from courses.factories import CourseRunFactory
from ecommerce.factories import ProductFactory

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
