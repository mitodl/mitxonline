"""Tests for B2B API functions."""

import faker
import pytest
import pytz
from django.conf import settings
from mitol.common.utils import now_in_utc

from b2b import factories
from b2b.api import create_contract_run, validate_basket_for_b2b_purchase
from b2b.constants import B2B_RUN_TAG_FORMAT
from b2b.factories import ContractPageFactory
from courses.factories import CourseFactory
from ecommerce.api_test import create_basket
from ecommerce.factories import ProductFactory, UnlimitedUseDiscountFactory
from ecommerce.models import BasketDiscount, DiscountProduct
from main.utils import date_to_datetime

FAKE = faker.Factory.create()
pytestmark = [
    pytest.mark.django_db,
]


@pytest.mark.parametrize(
    (
        "has_start",
        "has_end",
    ),
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_create_single_course_run(mocker, has_start, has_end):
    """Test that a single course run is created correctly for a contract."""

    now_time = now_in_utc()
    mocker.patch("b2b.api.now_in_utc", return_value=now_time)

    contract = factories.ContractPageFactory(
        contract_start=FAKE.past_datetime(tzinfo=pytz.timezone(settings.TIME_ZONE))
        if has_start
        else None,
        contract_end=FAKE.future_datetime(tzinfo=pytz.timezone(settings.TIME_ZONE))
        if has_end
        else None,
    )
    course = CourseFactory()
    run, product = create_contract_run(contract, course)

    assert run.course == course
    assert run.run_tag == B2B_RUN_TAG_FORMAT.format(
        org_id=contract.organization.id, contract_id=contract.id
    )
    assert run.b2b_contract == contract

    if has_start:
        assertable_start = date_to_datetime(contract.contract_start, settings.TIME_ZONE)
    else:
        assertable_start = now_time
    assert run.start_date == assertable_start
    assert run.enrollment_start == assertable_start
    assert run.certificate_available_date == assertable_start

    if has_end:
        assert run.end_date == date_to_datetime(
            contract.contract_end, settings.TIME_ZONE
        )
        assert run.enrollment_end == date_to_datetime(
            contract.contract_end, settings.TIME_ZONE
        )
    else:
        assert run.end_date is None
        assert run.enrollment_end is None

    assert product.purchasable_object == run


@pytest.mark.parametrize(
    (
        "run_contract",
        "apply_code",
    ),
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_b2b_basket_validation(user, run_contract, apply_code):
    """
    Test that a basket is validated correctly for B2B contracts.

    Basically, if the user is adding a product that links to a course run that
    is also linked to a contract, we need to have also applied the discount code
    that matches the product, or we shouldn't be allowed to buy it.

    The truth table for this should be:

    | run_contract | apply_code | result |
    |--------------|------------|--------|
    | False        | False      | True   |
    | False        | True       | True   |
    | True         | False      | False  |
    | True         | True       | True  |
    """

    product = ProductFactory.create()
    discount = UnlimitedUseDiscountFactory.create()
    discount_product = DiscountProduct.objects.create(
        discount=discount, product=product
    )
    discount_product.save()
    discount.products.add(discount_product)

    if run_contract:
        contract = ContractPageFactory.create()

        product.purchasable_object.b2b_contract = contract
        product.purchasable_object.save()
        product.refresh_from_db()

    basket = create_basket(user, [product])

    if apply_code:
        redemption = BasketDiscount(
            redemption_date=now_in_utc(),
            redeemed_by=user,
            redeemed_discount=discount,
            redeemed_basket=basket,
        )

        redemption.save()
        basket.refresh_from_db()

    check_result = validate_basket_for_b2b_purchase(basket)

    if run_contract and not apply_code:
        # User is trying to buy something that's linked to a contract but hasn't
        # applied the code, so this should be false.
        assert check_result is False
    else:
        assert check_result is True
