"""Tests for B2B API functions."""

from decimal import Decimal

import faker
import pytest
import pytz
from django.conf import settings
from mitol.common.utils import now_in_utc

from b2b import factories
from b2b.api import (
    create_contract_run,
    ensure_enrollment_codes_exist,
    validate_basket_for_b2b_purchase,
)
from b2b.constants import (
    B2B_RUN_TAG_FORMAT,
    CONTRACT_INTEGRATION_NONSSO,
    CONTRACT_INTEGRATION_SSO,
)
from b2b.factories import ContractPageFactory
from courses.factories import CourseFactory
from ecommerce.api_test import create_basket
from ecommerce.constants import REDEMPTION_TYPE_ONE_TIME, REDEMPTION_TYPE_UNLIMITED
from ecommerce.factories import (
    ProductFactory,
    UnlimitedUseDiscountFactory,
)
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


@pytest.mark.parametrize(
    (
        "is_sso",
        "has_price",
        "has_learner_cap",
        "update_change_price",
        "update_no_price",
        "update_sso",
    ),
    [
        (False, False, False, False, False, False),
        (False, False, True, False, False, False),
        (False, True, False, False, False, False),
        (False, True, True, False, False, False),
        (True, False, False, False, False, False),
        (True, False, True, False, False, False),
        (True, True, False, False, False, False),
        (True, True, True, False, False, False),
        (False, False, False, True, False, False),
        (False, False, True, True, False, False),
        (False, True, False, True, False, False),
        (False, True, True, True, False, False),
        (False, False, False, False, True, False),
        (False, False, True, False, True, False),
        (True, False, False, True, False, False),
        (True, False, True, True, False, False),
        (True, True, False, True, False, False),
        (True, True, True, True, False, False),
        (True, True, False, False, False, True),
        (True, True, True, False, False, True),
        (False, False, False, False, False, True),
        (False, False, True, False, False, True),
        (False, True, False, False, False, True),
        (False, True, True, False, False, True),
    ],
)
def test_ensure_enrollment_codes(  # noqa: PLR0913
    mocker,
    is_sso,
    has_price,
    has_learner_cap,
    update_change_price,
    update_no_price,
    update_sso,
):
    """
    Test that the enrollment codes are created correctly for a contract.

    This tests scenarios where contract data changes, which should also change
    the discounts that are created.

    These are the scenarios in order (run each with a learner cap and without):
    - Just create fixed-price $0 discounts for non-sso contract
    - Just create discounts for contract price for non-sso contract
    - Just create fixed-price $0 discounts for sso contract
    - Just create discounts for contract price for sso contract
    - fixed-price $0 discount to random new price
    - priced discount to new price discount
    - fixed-price $0 discount to no price - this should be a no-op
    - sso fixed-price $0 discount to random new price
    - sso price discount to new price discount
    - sso price discount to non-sso - should also no-op
    - non-sso fixed-price $0 discount to sso - should remove all discounts
    - non-sso price to sso - should no-op
    """

    mocked_ensure_call = mocker.patch("b2b.tasks.queue_enrollment_code_check.delay")
    max_learners = FAKE.random_int(min=1, max=15) if has_learner_cap else None
    price = FAKE.random_int(min=0, max=100) if has_price else None
    assert_price = price if price else Decimal(0)

    contract = factories.ContractPageFactory(
        integration_type=CONTRACT_INTEGRATION_SSO
        if is_sso
        else CONTRACT_INTEGRATION_NONSSO,
        enrollment_fixed_price=price,
        max_learners=max_learners,
    )
    course = CourseFactory()

    assert contract.get_discounts().count() == 0

    _, product = create_contract_run(contract, course)
    assert mocked_ensure_call.called

    ensure_enrollment_codes_exist(contract)

    if is_sso and not has_price:
        assert contract.get_discounts().count() == 0
    else:
        assert (
            contract.get_discounts().count() == max_learners if has_learner_cap else 1
        )

    for code in contract.get_discounts():
        assert code.amount == assert_price
        assert code.products.filter(product=product).exists()
        if has_learner_cap:
            assert code.redemption_type == REDEMPTION_TYPE_ONE_TIME
        else:
            assert code.redemption_type == REDEMPTION_TYPE_UNLIMITED

    # If the contract is updated later, the codes should also be updated accordingly.
    # Specifically:
    # - If we've changed the price, the discounts should also change amounts.
    # - If we've removed the price, the discounts should be set to 0.
    # - If we've set the price to zero and changed to SSO integration, we should
    #   no longer have discounts.
    if update_no_price or update_sso or update_change_price:
        if update_change_price:
            price = FAKE.random_int(min=0, max=100)
            assert_price = price if price else Decimal(0)
            contract.enrollment_fixed_price = price
        if update_no_price:
            contract.enrolment_fixed_price = None
        if update_sso:
            contract.integration_type = (
                CONTRACT_INTEGRATION_NONSSO if is_sso else CONTRACT_INTEGRATION_SSO
            )

        contract.save()
        ensure_enrollment_codes_exist(contract)

        if update_no_price and update_sso and not is_sso:
            # This is the last case, so we shouldn't have discounts now.
            # Test on our flags, not the contract, so we can make sure the contract
            # is also correct.
            assert contract.get_discounts().count() == 0
        else:
            # Otherwise we're really just making sure the price is updated.
            for code in contract.get_discounts():
                assert code.amount == assert_price
                assert code.products.filter(product=product).exists()
