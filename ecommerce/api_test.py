"""Tests for Ecommerce api"""

import logging
import random
import uuid
from datetime import datetime

import pytest
import pytz
import reversion
from CyberSource.rest import ApiException
from django.conf import settings
from django.urls import reverse
from factory import Faker, fuzzy
from mitol.payment_gateway.api import ProcessorResponse
from reversion.models import Version

from courses.factories import CourseRunEnrollmentFactory
from ecommerce.api import (
    check_and_process_pending_orders_for_resolution,
    check_for_duplicate_discount_redemptions,
    process_cybersource_payment_response,
    refund_order,
    unenroll_learner_from_order,
)
from ecommerce.constants import TRANSACTION_TYPE_PAYMENT, TRANSACTION_TYPE_REFUND
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
    BasketItem,
    DiscountRedemption,
    FulfilledOrder,
    Order,
    Transaction,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def fulfilled_order():
    """Fixture for creating a fulfilled order"""
    return OrderFactory.create(state=Order.STATE.FULFILLED)


@pytest.fixture()
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


@pytest.fixture()
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


@pytest.fixture()
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


@pytest.fixture
def user(db):
    """Creates a user"""
    return UserFactory.create()


@pytest.fixture(autouse=True)
def payment_gateway_settings():
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURITY_KEY = "Test Security Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY = "Test Access Key"
    settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def mock_create_run_enrollments(mocker):
    return mocker.patch("courses.api.create_run_enrollments", autospec=True)


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
        product=products[random.randrange(0, len(products))], basket=basket, quantity=1
    )
    basket_item.save()

    return basket


@pytest.mark.parametrize(
    "order_state",
    [
        Order.STATE.REFUNDED,
        Order.STATE.ERRORED,
        Order.STATE.PENDING,
        Order.STATE.DECLINED,
        Order.STATE.CANCELED,
        Order.STATE.REVIEW,
    ],
)
def test_cybersource_refund_no_fulfilled_order(order_state):
    """Test that refund_order returns logs properly and False when there is no Fulfilled order against
    the given order_id"""

    unfulfilled_order = OrderFactory.create(state=order_state)
    refund_response, message = refund_order(order_id=unfulfilled_order.id)
    assert f"Order with order_id {unfulfilled_order.id} is not in fulfilled state."
    assert refund_response is False
    assert "is not in fulfilled state." in message


def test_cybersource_refund_no_order_id():
    """Test that refund_order returns logs properly and False when there is no Fulfilled order against
    the given order_id"""

    refund_response, message = refund_order()
    assert f"Either order_id or reference_number is required to fetch the Order."
    assert refund_response is False
    assert "Either order_id or reference_number" in message


def test_cybersource_order_no_transaction(fulfilled_order):
    """
    Test that refund_order returns False when there is no transaction against a fulfilled order
    Ideally, there should be a payment type transaction for a fulfilled order
    """

    fulfilled_order = OrderFactory.create(state=Order.STATE.FULFILLED)
    refund_response, message = refund_order(order_id=fulfilled_order.id)
    assert f"There is no associated transaction against order_id {fulfilled_order.id}."
    assert refund_response is False
    assert "There is no associated transaction" in message


@pytest.mark.parametrize(
    "order_state, unenroll",
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
        with pytest.raises(Exception) as e:
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
    assert fulfilled_transaction.order.state == Order.STATE.REFUNDED


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
    assert message is ""

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
    assert fulfilled_transaction.order.state == Order.STATE.REFUNDED


def test_order_refund_failure(mocker, fulfilled_transaction):
    """Test that refund operation returns False when there was a failure in refund"""
    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        side_effect=ApiException(),
    )
    downgrade_task_mock = mocker.patch(
        "ecommerce.tasks.perform_downgrade_from_order.delay"
    )

    with pytest.raises(ApiException):
        refund_response, message = refund_order(order_id=fulfilled_transaction.order.id)
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

    with pytest.raises(Exception) as exc:
        refund_response = refund_order(order_id=fulfilled_transaction.order.id)
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

    with pytest.raises(Exception) as exc:
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


def test_process_cybersource_payment_response(
    settings, rf, mocker, user_client, user, products
):
    """Test that ensures the response from Cybersource for an ACCEPTed payment updates the orders state"""

    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
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

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    request = rf.post(reverse("checkout_result_api"), payload)

    # This is checked on the BackofficeCallbackView and CheckoutCallbackView POST endpoints
    # since we expect to receive a response to both from Cybersource.  If the current state is
    # PENDING, then we should process the response.
    assert order.state == Order.STATE.PENDING
    result = process_cybersource_payment_response(request, order)
    assert result == Order.STATE.FULFILLED


@pytest.mark.parametrize("include_discount", [True, False])
def test_process_cybersource_payment_decline_response(
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

    order = Order.objects.get(state=Order.STATE.PENDING, purchaser=user)

    assert order.reference_number == payload["req_reference_number"]

    if include_discount:
        discount = UnlimitedUseDiscountFactory.create()
        redemption = DiscountRedemption(
            redeemed_by=user,
            redeemed_discount=discount,
            redeemed_order=order,
            redemption_date=datetime.now(pytz.timezone(settings.TIME_ZONE)),
        ).save()
        order.refresh_from_db()

    request = rf.post(reverse("checkout_result_api"), payload)

    # This is checked on the BackofficeCallbackView and CheckoutCallbackView POST endpoints
    # since we expect to receive a response to both from Cybersource.  If the current state is
    # PENDING, then we should process the response.
    assert order.state == Order.STATE.PENDING

    if include_discount:
        assert order.discounts.count() > 0

    result = process_cybersource_payment_response(request, order)
    assert result == Order.STATE.DECLINED
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
    order = OrderFactory.create(state=Order.STATE.PENDING)

    # mocking out the create_enrollment and create_paid_courserun calls
    # we don't really care that it hits edX for this
    mocker.patch(
        "ecommerce.models.FulfillableOrder.create_enrollments", return_value=True
    )
    mocker.patch(
        "ecommerce.models.FulfillableOrder.create_paid_courseruns", return_value=True
    )

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
        order.state = Order.STATE.CANCELED
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
        assert order.state == Order.STATE.CANCELED
        assert (fulfilled, cancelled, errored) == (0, 1, 0)
    else:
        order.refresh_from_db()
        assert order.state == Order.STATE.FULFILLED
        assert (fulfilled, cancelled, errored) == (1, 0, 0)


@pytest.mark.parametrize("peruser", [True, False])
def test_duplicate_redemption_check(peruser):
    """
    Tests the check for multiple discount redemptions. Set peruser to test a
    one-time-per-user discount.
    """

    def make_stuff(user, discount):
        """Helper function to DRY out the rest of the test"""
        order = OrderFactory.create(purchaser=user, state=Order.STATE.FULFILLED)
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
    first_redemption = make_stuff(user, discount)

    if not peruser:
        user = UserFactory.create()

    second_redemption = make_stuff(user, discount)

    seen_ids = check_for_duplicate_discount_redemptions()

    assert discount.id in seen_ids
