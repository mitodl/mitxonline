"""Tests for B2B API functions."""

from decimal import Decimal

import faker
import pytest
import pytz
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from mitol.common.utils import now_in_utc
from opaque_keys.edx.keys import CourseKey

from b2b import factories
from b2b.api import (
    create_b2b_enrollment,
    create_contract_run,
    ensure_enrollment_codes_exist,
    validate_basket_for_b2b_purchase,
)
from b2b.constants import (
    B2B_RUN_TAG_FORMAT,
    CONTRACT_INTEGRATION_NONSSO,
    CONTRACT_INTEGRATION_SSO,
)
from b2b.exceptions import SourceCourseIncompleteError, TargetCourseRunExistsError
from b2b.factories import ContractPageFactory
from courses.factories import CourseFactory, CourseRunFactory
from courses.models import CourseRunEnrollment
from ecommerce.api_test import create_basket
from ecommerce.constants import REDEMPTION_TYPE_ONE_TIME, REDEMPTION_TYPE_UNLIMITED
from ecommerce.factories import (
    BasketFactory,
    BasketItemFactory,
    ProductFactory,
    UnlimitedUseDiscountFactory,
)
from ecommerce.models import Basket, BasketDiscount, DiscountProduct
from main.constants import (
    USER_MSG_TYPE_B2B_DISALLOWED,
    USER_MSG_TYPE_B2B_ENROLL_SUCCESS,
    USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT,
    USER_MSG_TYPE_B2B_ERROR_NO_PRODUCT,
    USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT,
)
from main.utils import date_to_datetime
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.factories import UserFactory

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
def test_create_single_course_run(mocker, contract_ready_course, has_start, has_end):
    """Test that a single course run is created correctly for a contract."""

    now_time = now_in_utc()
    mocker.patch("b2b.api.now_in_utc", return_value=now_time)
    mocker.patch("openedx.tasks.clone_courserun.delay")

    contract = factories.ContractPageFactory(
        contract_start=FAKE.past_datetime(tzinfo=pytz.timezone(settings.TIME_ZONE))
        if has_start
        else None,
        contract_end=FAKE.future_datetime(tzinfo=pytz.timezone(settings.TIME_ZONE))
        if has_end
        else None,
    )
    (source_course, _) = contract_ready_course
    run, product = create_contract_run(contract, source_course)

    assert run.course == source_course
    assert run.run_tag == B2B_RUN_TAG_FORMAT.format(
        year=now_time.year, contract_id=contract.id
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
    contract_ready_course,
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

    mocker.patch("openedx.tasks.clone_courserun.delay")
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
    (course, _) = contract_ready_course

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


@pytest.mark.parametrize("user_authenticated", [True, False])
@pytest.mark.parametrize("user_in_contract", [True, False])
@pytest.mark.parametrize("product_in_contract", [True, False])
@pytest.mark.parametrize("price_is_zero", [True, False])
@pytest.mark.parametrize("cart_has_products", [True, False])
@pytest.mark.parametrize("cart_has_discounts", [True, False])
def test_create_b2b_enrollment(  # noqa: PLR0913, C901, PLR0915
    mocker,
    contract_ready_course,
    settings,
    user_authenticated,
    user_in_contract,
    product_in_contract,
    price_is_zero,
    cart_has_products,
    cart_has_discounts,
):
    """
    Test B2B enrollment generation.

    create_b2b_enrollment should check that we're allowed to enroll in the B2B
    courserun, and then create and process a basket for the user. If there's an
    enrollment code, it should use one. If the price specified is non-zero, that
    should be caught by the enrollment code.
    """

    mocker.patch("openedx.tasks.clone_courserun.delay")
    mocker.patch("openedx.api.enroll_in_edx_course_runs")
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "a token"  # noqa: S105
    settings.OPENEDX_SERVICE_WORKER_USERNAME = "a username"

    contract = ContractPageFactory.create(
        integration_type=CONTRACT_INTEGRATION_SSO,
        enrollment_fixed_price=Decimal(0)
        if price_is_zero
        else FAKE.pydecimal(left_digits=2, right_digits=2, positive=True),
    )
    (course, _) = contract_ready_course
    run, product = create_contract_run(contract, course)

    if not product_in_contract:
        # just create something random - this is like someone fuzzing the API
        product = ProductFactory.create()

    if user_authenticated:
        user = UserFactory.create()
        if user_in_contract:
            user.b2b_contracts.add(contract)
            user.save()

        assert Basket.objects.filter(user=user).count() == 0

        if cart_has_products:
            # create a basket - we should clear it out
            existing_basket = BasketFactory.create(user=user)
            BasketItemFactory(basket=existing_basket)

            if cart_has_discounts:
                # also put discounts in it!
                random_discount = UnlimitedUseDiscountFactory.create()
                BasketDiscount.objects.create(
                    redemption_date=now_in_utc(),
                    redeemed_by=user,
                    redeemed_discount=random_discount,
                    redeemed_basket=existing_basket,
                )

    else:
        user = AnonymousUser()

    # the request itself doesn't matter - we just need an object with a user in it
    request = RequestFactory().get("/")
    request.user = user

    result = create_b2b_enrollment(request, product)

    assert "result" in result

    if user_authenticated:
        # You should not have a basket by default. If you do, we should clear it
        # when you hit the enroll API.
        if not user_in_contract or not product_in_contract:
            assert_test = 1 if cart_has_products else 0
            assert Basket.objects.filter(user=user).count() == assert_test

        if not product_in_contract:
            assert result["result"] == USER_MSG_TYPE_B2B_ERROR_NO_PRODUCT
            return

        if not user_in_contract:
            assert result["result"] == USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT
            return

        if not price_is_zero:
            # Success, other than the price. We should bounce the user to the cart
            # page if the price isn't zero.
            assert result["result"] == USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT
            assert Basket.objects.filter(user=user).count() == 1
            test_basket = Basket.objects.filter(user=user).get()
            assert test_basket.basket_items.filter(product=product).exists()
            my_run_qs = CourseRunEnrollment.objects.filter(
                user=user, run=run, active=True
            )
            assert my_run_qs.count() == 0
            return

        # This is the success state.
        assert result["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS
        assert Basket.objects.filter(user=user).count() == 0

        my_run_qs = CourseRunEnrollment.objects.filter(user=user, run=run, active=True)
        assert my_run_qs.count() == 1
        my_run = my_run_qs.first()
        assert my_run
        assert my_run.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE
    else:
        assert result["result"] == USER_MSG_TYPE_B2B_DISALLOWED


@pytest.mark.parametrize(
    "run_exists",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize("source_run_exists", [True, False])
def test_create_contract_run(mocker, source_run_exists, run_exists):
    """
    Test creating runs for a contract.

    When we add courseware to a contract, we should check and create a run for
    the course. The run should have a readable ID in a known format. This should
    also queue up a course clone in edX.
    """

    contract = ContractPageFactory.create()
    course = CourseFactory.create()
    source_course_key = CourseKey.from_string(f"{course.readable_id}+SOURCE")
    mocked_clone_run = mocker.patch("openedx.tasks.clone_courserun.delay")
    this_year = now_in_utc().year

    if source_run_exists:
        # This should be the default, but need to test the case in which the
        # source run isn't configured.
        source_course_run_key = (
            f"course-v1:{source_course_key.org}+{source_course_key.course}+SOURCE"
        )
        CourseRunFactory.create(
            course=course, courseware_id=source_course_run_key, run_tag="SOURCE"
        )

    target_course_id = f"course-v1:UAI_{contract.organization.org_key}+{source_course_key.course}+{this_year}_C{contract.id}"

    if not source_run_exists:
        with pytest.raises(SourceCourseIncompleteError) as exc:
            create_contract_run(contract, course)

        assert "No course runs available" in str(exc)
        return

    if run_exists:
        collision_run = CourseRunFactory.create(
            course=course, courseware_id=target_course_id
        )

        with pytest.raises(TargetCourseRunExistsError) as exc:
            create_contract_run(contract, course)

        target_course_key = CourseKey.from_string(collision_run.courseware_id)
        assert f"courseware ID {target_course_key} already exists" in str(exc)
        return

    assert not course.courseruns.filter(courseware_id=target_course_id).exists()

    created_run, created_product = create_contract_run(contract, course)

    assert course.courseruns.filter(courseware_id=target_course_id).exists()
    assert created_run.courseware_id == target_course_id
    assert created_product.object_id == created_run.id

    mocked_clone_run.assert_called()
