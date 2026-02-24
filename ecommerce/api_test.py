"""Tests for Ecommerce api"""

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import freezegun
import pytest
import reversion
from CyberSource.rest import ApiException
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from factory import Faker, fuzzy
from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.api import ProcessorResponse
from reversion.models import Version

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)
from ecommerce.api import (
    apply_discount_to_basket,
    check_and_process_pending_orders_for_resolution,
    check_for_duplicate_discount_redemptions,
    create_verified_program_course_run_enrollment,
    create_verified_program_discount,
    get_auto_apply_discounts_for_basket,
    process_cybersource_payment_response,
    refund_order,
    unenroll_learner_from_order,
)
from ecommerce.constants import (
    DISCOUNT_TYPE_FIXED_PRICE,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
)
from ecommerce.exceptions import (
    VerifiedProgramInvalidBasketError,
    VerifiedProgramNoEnrollmentError,
)
from ecommerce.factories import (
    DiscountRedemptionFactory,
    LineFactory,
    OneTimeDiscountFactory,
    OneTimePerUserDiscountFactory,
    OrderFactory,
    ProductFactory,
    TransactionFactory,
    UnlimitedUseDiscountFactory,
)
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    DiscountProduct,
    DiscountRedemption,
    FulfilledOrder,
    Order,
    OrderStatus,
    Product,
    Transaction,
    UserDiscount,
)
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory, FlexiblePriceTierFactory
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def fulfilled_order():
    """Fixture for creating a fulfilled order"""
    return OrderFactory.create(state=OrderStatus.FULFILLED)


@pytest.fixture
def fulfilled_transaction(fulfilled_order):
    """Fixture to creating a fulfilled transaction"""
    payment_amount = 10.00
    fulfilled_sample = {
        "transaction_id": "1234",
        "req_amount": payment_amount,
        "req_currency": "USD",
    }

    return TransactionFactory.create(
        transaction_id="1234",
        transaction_type=TRANSACTION_TYPE_PAYMENT,
        data=fulfilled_sample,
        order=fulfilled_order,
    )


@pytest.fixture
def fulfilled_paypal_transaction(fulfilled_order):
    """Fixture to creating a fulfilled transaction"""
    payment_amount = 10.00
    fulfilled_sample = {
        "transaction_id": "1234",
        "req_amount": payment_amount,
        "req_currency": "USD",
        "paypal_token": "EC-" + str(fuzzy.FuzzyText(length=17)),
        "paypal_payer_id": str(fuzzy.FuzzyText(length=13)),
        "paypal_fee_amount": payment_amount,
        "paypal_payer_status": "unverified",
        "paypal_address_status": "Confirmed",
        "paypal_customer_email": str(Faker("ascii_email")),
        "paypal_payment_status": "Completed",
        "paypal_pending_reason": "order",
    }

    return TransactionFactory.create(
        transaction_id="1234",
        transaction_type=TRANSACTION_TYPE_PAYMENT,
        data=fulfilled_sample,
        order=fulfilled_order,
    )


@pytest.fixture
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


@pytest.fixture
def user(db):
    """Creates a user"""
    return UserFactory.create()


@pytest.fixture(autouse=True)
def mock_create_run_enrollments(mocker):
    return mocker.patch("courses.api.create_run_enrollments", autospec=True)


@pytest.fixture
def mock_hubspot_order(mocker):
    """Mock sync_deal_with_hubspot."""

    return mocker.patch("hubspot_sync.api.sync_deal_with_hubspot")


@pytest.fixture
def bootstrapped_verified_program():
    """
    Returns a bootstrapped program.

    Bootstrapped means you get back:
    - a program
    - a product for the program
    - a course associated with the program (as a requirement)
    - a course run
    - a product for the course run

    Returns:
    - tuple of the above things in that order
    """
    program = ProgramFactory.create()
    prog_ctype = ContentType.objects.get_for_model(program)
    with reversion.create_revision():
        prog_product = Product.objects.create(
            content_type=prog_ctype,
            object_id=program.id,
            price=10,
        )

    courserun = CourseRunFactory.create()
    program.add_requirement(courserun.course)

    cr_ctype = ContentType.objects.get_for_model(courserun)
    with reversion.create_revision():
        cr_product = Product.objects.create(
            content_type=cr_ctype, object_id=courserun.id, price=10
        )

    return (
        program,
        prog_product,
        courserun.course,
        courserun,
        cr_product,
    )


def test_cybersource_refund_no_order():
    """Tests that refund_order throws FulfilledOrder.DoesNotExist exception when the order doesn't exist"""

    with pytest.raises(FulfilledOrder.DoesNotExist):
        refund_order(order_id=1)  # Caling refund with random Id


def create_basket(user, products):
    """
    Bootstraps a basket with a product in it for testing the discount
    redemption APIs
    TODO: this should probably just be a factory
    """
    basket = Basket(user=user)
    basket.save()

    basket_item = BasketItem(
        product=products[random.randrange(0, len(products))],  # noqa: S311
        basket=basket,
        quantity=1,
    )
    basket_item.save()

    return basket


@pytest.mark.parametrize(
    "order_state",
    [
        OrderStatus.REFUNDED,
        OrderStatus.ERRORED,
        OrderStatus.PENDING,
        OrderStatus.DECLINED,
        OrderStatus.CANCELED,
        OrderStatus.REVIEW,
    ],
)
def test_cybersource_refund_no_fulfilled_order(order_state):
    """Test that refund_order returns logs properly and False when there is no Fulfilled order against
    the given order_id
    """

    unfulfilled_order = OrderFactory.create(state=order_state)
    refund_response, message = refund_order(order_id=unfulfilled_order.id)
    assert f"Order with order_id {unfulfilled_order.id} is not in fulfilled state."  # noqa: PLW0129
    assert refund_response is False
    assert "is not in fulfilled state." in message


def test_cybersource_refund_no_order_id():
    """Test that refund_order returns logs properly and False when there is no Fulfilled order against
    the given order_id
    """

    refund_response, message = refund_order()
    assert "Either order_id or reference_number is required to fetch the Order."  # noqa: PLW0129
    assert refund_response is False
    assert "Either order_id or reference_number" in message


def test_cybersource_order_no_transaction(fulfilled_order):
    """
    Test that refund_order returns False when there is no transaction against a fulfilled order
    Ideally, there should be a payment type transaction for a fulfilled order
    """

    fulfilled_order = OrderFactory.create(state=OrderStatus.FULFILLED)
    refund_response, message = refund_order(order_id=fulfilled_order.id)
    assert f"There is no associated transaction against order_id {fulfilled_order.id}."  # noqa: PLW0129
    assert refund_response is False
    assert "There is no associated transaction" in message


@pytest.mark.parametrize(
    "order_state, unenroll",  # noqa: PT006
    [
        (ProcessorResponse.STATE_PENDING, True),
        (ProcessorResponse.STATE_DUPLICATE, True),
        (ProcessorResponse.STATE_PENDING, False),
        (ProcessorResponse.STATE_DUPLICATE, False),
    ],
)
def test_order_refund_success(mocker, order_state, unenroll, fulfilled_transaction):
    """Test that appropriate data is created for a successful refund and it's state changes to REFUNDED"""
    sample_response_data = {
        "id": "12345",  # it only has id in refund response, no transaction_id
        "refundAmountDetails": {"refundAmount": float(fulfilled_transaction.amount)},
    }
    sample_response = ProcessorResponse(
        state=order_state,
        response_data=sample_response_data,
        transaction_id="1234",
        message="",
        response_code="",
    )
    downgrade_task_mock = mocker.patch(
        "ecommerce.tasks.perform_downgrade_from_order.delay"
    )

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        return_value=sample_response,
    )

    if order_state == ProcessorResponse.STATE_DUPLICATE:
        with pytest.raises(Exception) as e:  # noqa: PT011, F841
            refund_success, _ = refund_order(
                order_id=fulfilled_transaction.order.id, unenroll=unenroll
            )

        return
    else:
        refund_success, _ = refund_order(
            order_id=fulfilled_transaction.order.id, unenroll=unenroll
        )

    # There should be two transaction objects (One for payment and other for refund)
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_PAYMENT,
        ).count()
        == 1
    )
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 1
    )
    assert refund_success is True

    # Unenrollment task should only run if unenrollment was requested
    if unenroll:
        downgrade_task_mock.assert_called_once_with(fulfilled_transaction.order.id)
    else:
        assert not downgrade_task_mock.called

    # Refund transaction object should have appropriate data
    refund_transaction = Transaction.objects.filter(
        order=fulfilled_transaction.order.id, transaction_type=TRANSACTION_TYPE_REFUND
    ).first()

    assert refund_transaction.data == sample_response_data
    assert refund_transaction.amount == fulfilled_transaction.amount

    # The state of the order should be REFUNDED after a successful refund
    fulfilled_transaction.order.refresh_from_db()
    assert fulfilled_transaction.order.state == OrderStatus.REFUNDED


@pytest.mark.parametrize("unenroll", [True, False])
def test_order_refund_success_with_ref_num(mocker, unenroll, fulfilled_transaction):
    """Test a successful refund based only on reference number"""
    sample_response_data = {
        "id": "12345",
        "refundAmountDetails": {"refundAmount": float(fulfilled_transaction.amount)},
    }
    sample_response = ProcessorResponse(
        state=ProcessorResponse.STATE_PENDING,
        response_data=sample_response_data,
        transaction_id="1234",
        message="",
        response_code="",
    )
    downgrade_task_mock = mocker.patch(
        "ecommerce.tasks.perform_downgrade_from_order.delay"
    )

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        return_value=sample_response,
    )
    refund_success, message = refund_order(
        reference_number=fulfilled_transaction.order.reference_number, unenroll=unenroll
    )
    # There should be two transaction objects (One for payment and other for refund)
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_PAYMENT,
        ).count()
        == 1
    )
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 1
    )
    assert refund_success is True
    assert message == ""

    # Unenrollment task should only run if unenrollment was requested
    if unenroll:
        downgrade_task_mock.assert_called_once_with(fulfilled_transaction.order.id)
    else:
        assert not downgrade_task_mock.called

    # Refund transaction object should have appropriate data
    refund_transaction = Transaction.objects.filter(
        order=fulfilled_transaction.order.id, transaction_type=TRANSACTION_TYPE_REFUND
    ).first()

    assert refund_transaction.data == sample_response_data
    assert refund_transaction.amount == fulfilled_transaction.amount

    # The state of the order should be REFUNDED after a successful refund
    fulfilled_transaction.order.refresh_from_db()
    assert fulfilled_transaction.order.state == OrderStatus.REFUNDED


def test_order_refund_failure(mocker, fulfilled_transaction):
    """Test that refund operation returns False when there was a failure in refund"""
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        side_effect=ApiException(),
    )
    downgrade_task_mock = mocker.patch(
        "ecommerce.tasks.perform_downgrade_from_order.delay"
    )

    with pytest.raises(ApiException):  # noqa: PT012
        refund_response, _ = refund_order(order_id=fulfilled_transaction.order.id)
        assert refund_response is False
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 0
    )
    # Unenrollment task should not run when API fails
    assert not downgrade_task_mock.called


def test_order_refund_failure_no_exception(mocker, fulfilled_transaction):
    """Test that refund operation throws an exception if the gateway returns an error state"""
    error_return = {
        "state": ProcessorResponse.STATE_ERROR,
        "message": "This is an error message. Testing 123456",
    }

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        returns=error_return,
    )
    downgrade_task_mock = mocker.patch(
        "ecommerce.tasks.perform_downgrade_from_order.delay"
    )

    with pytest.raises(Exception) as exc:  # noqa: PT011, PT012
        refund_response = refund_order(order_id=fulfilled_transaction.order.id)  # noqa: F841
        assert "Testing 123456" in str(exc)

    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 0
    )
    # Unenrollment task should not run when API fails
    assert not downgrade_task_mock.called


def test_paypal_refunds(fulfilled_paypal_transaction):
    """PayPal transactions should fail before they get to the payment gateway."""

    with pytest.raises(Exception) as exc:  # noqa: PT011, PT012
        refund_order(order_id=fulfilled_paypal_transaction.order.id)
        assert "PayPal" in exc


def test_unenrollment_unenrolls_learner(mocker, user):
    """
    Test that unenroll_learner_from_order unenrolls the learner from an order
    """
    order = OrderFactory.create(purchaser=user)
    with reversion.create_revision():
        product = ProductFactory.create()
    version = Version.objects.get_for_object(product).first()
    enrollment = CourseRunEnrollmentFactory.create(user=user)
    LineFactory.create(
        order=order, purchased_object=enrollment.run, product_version=version
    )

    unenroll_mock = mocker.patch(
        "ecommerce.api.deactivate_run_enrollment",
        return_value=enrollment,
    )
    unenroll_learner_from_order(order_id=order.id)
    unenroll_mock.assert_called()


@pytest.mark.skip_nplusone_check
def test_process_cybersource_payment_response(  # noqa: PLR0913
    settings, rf, mocker, user_client, user, products
):
    """Test that ensures the response from Cybersource for an ACCEPTed payment updates the orders state"""

    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=True,
    )
    create_basket(user, products)

    resp = user_client.post(reverse("checkout_api-start_checkout"))

    payload = resp.json()["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": "ACCEPT",
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    order = Order.objects.get(state=OrderStatus.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    request = rf.post(reverse("checkout_result_api"), payload)

    # This is checked on the BackofficeCallbackView and CheckoutCallbackView POST endpoints
    # since we expect to receive a response to both from Cybersource.  If the current state is
    # PENDING, then we should process the response.
    assert order.state == OrderStatus.PENDING
    result = process_cybersource_payment_response(request, order)
    assert result == OrderStatus.FULFILLED


@pytest.mark.skip_nplusone_check
@pytest.mark.parametrize("include_discount", [True, False])
def test_process_cybersource_payment_decline_response(  # noqa: PLR0913
    rf, mocker, user_client, user, products, include_discount
):
    """Test that ensures the response from Cybersource for an DECLINEd payment updates the orders state"""

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.validate_processor_response",
        return_value=True,
    )
    create_basket(user, products)

    resp = user_client.post(reverse("checkout_api-start_checkout"))

    payload = resp.json()["payload"]
    payload = {
        **{f"req_{key}": value for key, value in payload.items()},
        "decision": "DECLINE",
        "message": "payment processor message",
        "transaction_id": "12345",
    }

    order = Order.objects.get(state=OrderStatus.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    if include_discount:
        discount = UnlimitedUseDiscountFactory.create()
        redemption = DiscountRedemption(  # noqa: F841
            redeemed_by=user,
            redeemed_discount=discount,
            redeemed_order=order,
            redemption_date=datetime.now(ZoneInfo(settings.TIME_ZONE)),
        ).save()
        order.refresh_from_db()

    request = rf.post(reverse("checkout_result_api"), payload)

    # This is checked on the BackofficeCallbackView and CheckoutCallbackView POST endpoints
    # since we expect to receive a response to both from Cybersource.  If the current state is
    # PENDING, then we should process the response.
    assert order.state == OrderStatus.PENDING

    if include_discount:
        assert order.discounts.count() > 0

    result = process_cybersource_payment_response(request, order)
    assert result == OrderStatus.DECLINED
    order.refresh_from_db()
    assert order.discounts.count() == 0


@pytest.mark.parametrize("test_type", [None, "fail", "empty"])
def test_check_and_process_pending_orders_for_resolution(mocker, test_type):
    """
    Tests the pending order check. test_type can be:
    - None - there's an order and it was found
    - fail - there's an order but the payment failed (failed status in CyberSource)
    - empty - order isn't pending
    """
    order = OrderFactory.create(state=OrderStatus.PENDING)

    # mocking out the create_enrollment and create_paid_courserun calls
    # we don't really care that it hits edX for this
    mocker.patch("ecommerce.models.OrderFlow.create_enrollments", return_value=True)

    test_payload = {
        "utf8": "",
        "message": "Request was processed successfully.",
        "decision": "100",
        "auth_code": "888888",
        "auth_time": "2023-02-09T20:06:51Z",
        "signature": "",
        "req_amount": "999",
        "req_locale": "en-us",
        "auth_amount": "999",
        "reason_code": "100",
        "req_currency": "USD",
        "auth_avs_code": "X",
        "auth_response": "100",
        "req_card_type": "",
        "request_token": "",
        "card_type_name": "",
        "req_access_key": "",
        "req_item_0_sku": "60-2",
        "req_profile_id": "2BA30484-75E7-4C99-A7D4-8BD7ADE4552D",
        "transaction_id": "6759732112426719104003",
        "req_card_number": "",
        "req_consumer_id": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
        "req_item_0_code": "60",
        "req_item_0_name": "course-v1:edX+E2E-101+course",
        "signed_date_time": "2023-02-09T20:06:51Z",
        "auth_avs_code_raw": "I1",
        "auth_trans_ref_no": "123456789619999",
        "bill_trans_ref_no": "123456789619999",
        "req_bill_to_email": "testlearner@odl.local",
        "req_payment_method": "card",
        "signed_field_names": "",
        "req_bill_to_surname": "LEARNER",
        "req_item_0_quantity": 1,
        "req_line_item_count": 1,
        "req_bill_to_forename": "TEST",
        "req_card_expiry_date": "02-2025",
        "req_reference_number": f"{order.reference_number}",
        "req_transaction_type": "sale",
        "req_transaction_uuid": "",
        "req_item_0_tax_amount": "0",
        "req_item_0_unit_price": "999",
        "req_customer_ip_address": "172.19.0.8",
        "req_bill_to_address_city": "Tallahasseeeeeeee",
        "req_bill_to_address_line1": "555 123 Place",
        "req_bill_to_address_state": "FL",
        "req_merchant_defined_data1": "1",
        "req_bill_to_address_country": "US",
        "req_bill_to_address_postal_code": "81992",
        "req_override_custom_cancel_page": "https://rc.mitxonline.mit.edu/checkout/result/",
        "req_override_custom_receipt_page": "https://rc.mitxonline.mit.edu/checkout/result/",
        "req_card_type_selection_indicator": "001",
    }

    retval = {}

    if test_type == "fail":
        test_payload["reason_code"] = "999"

    if test_type == "empty":
        order.state = OrderStatus.CANCELED
        order.save()
        order.refresh_from_db()

    if test_type is None or test_type == "fail":
        retval = {f"{order.reference_number}": test_payload}

    mocked_gateway_func = mocker.patch(
        "mitol.payment_gateway.api.CyberSourcePaymentGateway.find_and_get_transactions",
        return_value=retval,
    )

    (fulfilled, cancelled, errored) = check_and_process_pending_orders_for_resolution()

    if test_type == "empty":
        assert not mocked_gateway_func.called
        assert (fulfilled, cancelled, errored) == (0, 0, 0)
    elif test_type == "fail":
        order.refresh_from_db()
        assert order.state == OrderStatus.CANCELED
        assert (fulfilled, cancelled, errored) == (0, 1, 0)
    else:
        order.refresh_from_db()
        assert order.state == OrderStatus.FULFILLED
        assert (fulfilled, cancelled, errored) == (1, 0, 0)


@pytest.mark.parametrize("peruser", [True, False])
def test_duplicate_redemption_check(peruser):
    """
    Tests the check for multiple discount redemptions. Set peruser to test a
    one-time-per-user discount.
    """

    def make_stuff(user, discount):
        """Helper function to DRY out the rest of the test"""
        order = OrderFactory.create(purchaser=user, state=OrderStatus.FULFILLED)
        redemption = DiscountRedemptionFactory.create(
            redeemed_by=user, redeemed_discount=discount, redeemed_order=order
        )

        return (order, redemption)

    discount = (
        OneTimePerUserDiscountFactory.create()
        if peruser
        else OneTimeDiscountFactory.create()
    )

    user = UserFactory.create()
    first_redemption = make_stuff(user, discount)  # noqa: F841

    if not peruser:
        user = UserFactory.create()

    second_redemption = make_stuff(user, discount)  # noqa: F841

    seen_ids = check_for_duplicate_discount_redemptions()

    assert discount.id in seen_ids


def test_create_verified_program_discount():
    """Test that creating a special discount for programs works"""

    program = ProgramFactory.create()
    content_type = ContentType.objects.get_for_model(program)

    with reversion.create_revision():
        Product.objects.create(
            price=100, content_type=content_type, object_id=program.id
        )

    discount = create_verified_program_discount(program)

    assert discount
    assert discount.is_program_discount
    assert discount.products.filter(
        product__content_type=content_type, product__object_id=program.id
    ).exists()


def test_create_verified_program_course_run_enrollment(
    mock_create_run_enrollments, mock_hubspot_order, bootstrapped_verified_program, user
):
    """Test that creating a verified course run enrollment for a program works."""

    mock_cre_side_effect = mock_create_run_enrollments.side_effect

    (program, _, _, courserun, _) = bootstrapped_verified_program

    ProgramEnrollmentFactory.create(
        program=program, user=user, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    request = RequestFactory().get("/")
    request.user = user

    mock_create_run_enrollments.side_effect = (
        lambda user, runs, *, mode=EDX_ENROLLMENT_VERIFIED_MODE, **kwargs: (  # noqa: ARG005
            [
                CourseRunEnrollmentFactory.create(
                    run=runs[0], user=user, enrollment_mode=mode
                )
            ],
            False,
        )
    )

    cr_enrollment = create_verified_program_course_run_enrollment(
        request, courserun, program
    )

    assert cr_enrollment.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE

    mock_create_run_enrollments.side_effect = mock_cre_side_effect


def test_create_vpcre_no_program(bootstrapped_verified_program, user):
    """
    Test that creating a verified course run enrollment for a program fails if
    there's no program enrollment.
    """

    (program, _, _, courserun, _) = bootstrapped_verified_program

    request = RequestFactory().get("/")
    request.user = user

    with pytest.raises(VerifiedProgramNoEnrollmentError) as exc:
        create_verified_program_course_run_enrollment(request, courserun, program)

    assert "No verified enrollment" in str(exc.value)


def test_create_vpcre_bad_basket(
    mocker, mock_hubspot_order, bootstrapped_verified_program
):
    """
    Test that creating a verified course run enrollment for a program fails if
    the basket has other stuff in.
    """

    with reversion.create_revision():
        some_other_product = ProductFactory.create()

    (program, _, _, courserun, _) = bootstrapped_verified_program

    prog_enrollment = ProgramEnrollmentFactory.create(
        program=program, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    request = RequestFactory().get("/")
    request.user = prog_enrollment.user

    user_basket = Basket.objects.create(user=prog_enrollment.user)
    BasketItem.objects.create(
        basket=user_basket, product=some_other_product, quantity=1
    )

    with pytest.raises(VerifiedProgramInvalidBasketError) as exc:
        create_verified_program_course_run_enrollment(request, courserun, program)

    assert "not empty" in str(exc.value)


@pytest.mark.parametrize(
    "better_discount",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "is_valid",
    [
        True,
        False,
    ],
)
def test_apply_discount_to_basket(user, better_discount, is_valid):
    """
    Test that applying a discount to a basket works as expected.

    A new discount should only apply if it's valid (not expired, not finaid unless
    the flag is set, applies to the user/product in the basket) and it provides
    a better discount than anything else that's applied already.
    """

    run = CourseRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    basket, _ = Basket.objects.get_or_create(user=user)

    BasketItem.objects.create(basket=basket, product=product, quantity=1)

    existing_discount = UnlimitedUseDiscountFactory.create(
        amount=100, discount_type="fixed-price"
    )
    BasketDiscount.objects.create(
        redeemed_by=user,
        redemption_date=now_in_utc(),
        redeemed_discount=existing_discount,
        redeemed_basket=basket,
    )

    new_discount = UnlimitedUseDiscountFactory.create(
        amount=(50 if better_discount else 150), discount_type="fixed-price"
    )

    if not is_valid:
        new_discount.activation_date = now_in_utc() + timedelta(days=30)
        new_discount.save()

    apply_discount_to_basket(basket, new_discount)

    if better_discount and is_valid:
        assert basket.discounts.filter(redeemed_discount=new_discount).exists()
    else:
        assert basket.discounts.filter(redeemed_discount=existing_discount).exists()


@pytest.mark.parametrize(
    "is_better",
    [
        True,
        False,
    ],
)
def test_apply_discount_to_basket_with_user_discount(user, is_better):
    """
    Test that apply_discount_to_basket function works properly with a user discount applied.

    User discounts should take precedence over anything that the learner is
    applying, whether or not it's a better discount.
    """

    run = CourseRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    basket, _ = Basket.objects.get_or_create(user=user)

    BasketItem.objects.create(basket=basket, product=product, quantity=1)

    user_discount = UnlimitedUseDiscountFactory.create(
        amount=200, discount_type=DISCOUNT_TYPE_FIXED_PRICE
    )
    apply_discount = UnlimitedUseDiscountFactory.create(
        amount=(50 if is_better else 300), discount_type=DISCOUNT_TYPE_FIXED_PRICE
    )

    UserDiscount.objects.create(user=user, discount=user_discount)

    # Shortcut all the verifications for the user discount and just apply it
    # since we expect it to be there.
    BasketDiscount.objects.create(
        redeemed_by=user,
        redemption_date=now_in_utc(),
        redeemed_discount=user_discount,
        redeemed_basket=basket,
    )

    apply_discount_to_basket(basket, apply_discount)

    assert basket.discounts.count() == 1
    assert basket.discounts.filter(redeemed_discount=user_discount).exists()


@pytest.mark.parametrize("apply_finaid_first", [True, False])
def test_apply_discount_to_basket_with_user_discount_and_finaid(
    user, apply_finaid_first
):
    """
    Test that apply_discount_to_basket function works properly with a finaid discount
    and user discount applied.

    User discounts should take precedence over anything that the learner is
    applying, whether or not it's a better discount, unless there's a financial
    assistance discount applied.
    """

    run = CourseRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    basket, _ = Basket.objects.get_or_create(user=user)
    finaid_tier = FlexiblePriceTierFactory(courseware_object=run.course)
    FlexiblePriceFactory(
        user=user,
        courseware_object=run.course,
        tier=finaid_tier,
        status=FlexiblePriceStatus.APPROVED,
    )
    finaid_tier.discount.discount_type = DISCOUNT_TYPE_FIXED_PRICE
    finaid_tier.discount.amount = 100
    finaid_tier.discount.save()

    BasketItem.objects.create(basket=basket, product=product, quantity=1)

    user_discount = UnlimitedUseDiscountFactory.create(
        amount=200, discount_type=DISCOUNT_TYPE_FIXED_PRICE
    )
    UserDiscount.objects.create(user=user, discount=user_discount)

    BasketDiscount.objects.create(
        redeemed_by=user,
        redemption_date=now_in_utc(),
        redeemed_discount=finaid_tier.discount if apply_finaid_first else user_discount,
        redeemed_basket=basket,
    )

    apply_discount_to_basket(
        basket,
        user_discount if apply_finaid_first else finaid_tier.discount,
        allow_finaid=True,
    )

    assert basket.discounts.count() == 1
    assert basket.discounts.filter(redeemed_discount=finaid_tier.discount).exists()

    regular_discount = UnlimitedUseDiscountFactory.create(
        amount=50, discount_type=DISCOUNT_TYPE_FIXED_PRICE
    )
    apply_discount_to_basket(basket, regular_discount)

    assert basket.discounts.count() == 1
    # The finaid discount should override the user discount, so we should now
    # have the regular discount, because it's better.
    assert basket.discounts.filter(redeemed_discount=regular_discount).exists()


def test_get_auto_apply_discounts(user):  # noqa: PLR0915
    """
    Test that the auto-apply discount function works as expected.

    Depending on what the user's basket has in it, we should get back any of:
    - User discounts (if there's any assigned)
    - Financial assistance tier discount (if the user has finaid)
    - Discounts marked as "automatic"
    - Nothing, if none of these apply
    """

    run = CourseRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    basket, _ = Basket.objects.get_or_create(user=user)

    BasketItem.objects.create(basket=basket, product=product, quantity=1)

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 0

    # test with regular discounts
    # we'll assign one to the product, but that doesn't make it automatically
    # applicable (unless automatic=True). we'll add a user to the user one later.

    plain_discount = UnlimitedUseDiscountFactory.create(automatic=False)
    plain_attached_product_discount = UnlimitedUseDiscountFactory.create(
        automatic=False
    )
    plain_attached_user_discount = UnlimitedUseDiscountFactory.create(automatic=False)
    DiscountProduct.objects.create(
        discount=plain_attached_product_discount, product=product
    )

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 0

    # set the product discount to auto-apply, we should just see that now
    plain_attached_product_discount.automatic = True
    plain_attached_product_discount.save()

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 1
    assert plain_discount.id not in discounts.all().values_list("id", flat=True)
    assert plain_attached_product_discount.id in discounts.all().values_list(
        "id", flat=True
    )

    # attach the user, we should see both it and the auto product ones now
    UserDiscount.objects.create(discount=plain_attached_user_discount, user=user)
    plain_attached_user_discount.save()

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 2
    assert plain_discount.id not in discounts.all().values_list("id", flat=True)
    assert plain_attached_user_discount.id in discounts.all().values_list(
        "id", flat=True
    )

    # make the regular one auto too - now we should have 3
    plain_discount.automatic = True
    plain_discount.save()

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 3
    assert plain_discount.id in discounts.all().values_list("id", flat=True)

    # add some financial assistance discounts
    finaid_tier = FlexiblePriceTierFactory(courseware_object=run.course)
    FlexiblePriceFactory(
        user=user,
        courseware_object=run.course,
        tier=finaid_tier,
        status=FlexiblePriceStatus.APPROVED,
    )

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 4
    assert finaid_tier.discount.id in discounts.all().values_list("id", flat=True)

    # test with a new basket and a new product, but for the same user
    # we should get the plain discount and the user discount. we should _also_
    # get the product discount, because the discount itself is automatic (but
    # it won't apply, because it won't be valid)

    new_product = ProductFactory.create()
    basket.delete()
    basket = Basket.objects.create(user=user)
    BasketItem.objects.create(basket=basket, product=new_product)

    discounts = get_auto_apply_discounts_for_basket(basket.id)

    assert discounts.count() == 3
    assert plain_discount.id in discounts.all().values_list("id", flat=True)
    assert plain_attached_user_discount.id in discounts.all().values_list(
        "id", flat=True
    )
    assert plain_attached_product_discount.id in discounts.all().values_list(
        "id", flat=True
    )

    plain_attached_product_discount.automatic = False
    plain_attached_product_discount.save()

    # test with a new user, a new basket, and a new product
    # we should only see the plain_discount (because it got set to automatic
    # earlier and it's not attached to anything in particular)

    new_user = UserFactory.create()
    new_basket = Basket.objects.create(user=new_user)
    BasketItem.objects.create(basket=new_basket, product=new_product)

    discounts = get_auto_apply_discounts_for_basket(new_basket.id)

    assert discounts.count() == 1
    assert plain_discount.id in discounts.all().values_list("id", flat=True)


def test_get_auto_apply_discounts_respects_dates(user):
    """Test that the auto-apply discount function respects dates set on the Discount."""

    run = CourseRunFactory.create()
    product = ProductFactory.create(purchasable_object=run)
    basket, _ = Basket.objects.get_or_create(user=user)

    BasketItem.objects.create(basket=basket, product=product, quantity=1)

    # no dates
    plain_discount_1 = UnlimitedUseDiscountFactory.create(automatic=True)
    plain_discount_2 = UnlimitedUseDiscountFactory.create(automatic=True)

    discounts = get_auto_apply_discounts_for_basket(basket.id)
    assert discounts.count() == 2
    assert plain_discount_1.id in discounts.all().values_list("id", flat=True)
    assert plain_discount_2.id in discounts.all().values_list("id", flat=True)

    # expiration only
    plain_discount_1.expiration_date = now_in_utc() + timedelta(days=30)
    plain_discount_1.save()

    past_expiry = now_in_utc() - timedelta(days=30)
    with freezegun.freeze_time(past_expiry):
        plain_discount_2.expiration_date = past_expiry + timedelta(days=1)
        plain_discount_2.save()

    discounts = get_auto_apply_discounts_for_basket(basket.id)
    assert discounts.count() == 1
    assert plain_discount_1.id in discounts.all().values_list("id", flat=True)
    assert plain_discount_2.id not in discounts.all().values_list("id", flat=True)

    # activation - since discount 2 expires in the past, we shouldn't get any back now
    plain_discount_1.activation_date = now_in_utc() + timedelta(days=1)
    plain_discount_1.save()

    discounts = get_auto_apply_discounts_for_basket(basket.id)
    assert discounts.count() == 0
