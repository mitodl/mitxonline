"""Tests for Ecommerce api"""

import random
import pytest
import reversion
from django.http import HttpRequest
from django.urls import reverse
from django.conf import settings
import uuid
from reversion.models import Version
from courses.factories import CourseRunEnrollmentFactory
from ecommerce.api import (
    process_cybersource_payment_response,
    refund_order,
    unenroll_learner_from_order,
)
from ecommerce.models import Basket, BasketItem, FulfilledOrder, Order, Transaction
from ecommerce.factories import (
    OrderFactory,
    TransactionFactory,
    ProductFactory,
    LineFactory,
)
from ecommerce.constants import (
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
)
from mitol.payment_gateway.api import ProcessorResponse
from CyberSource.rest import ApiException
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
    refund_response = refund_order(order_id=unfulfilled_order.id)
    assert f"Order with order_id {unfulfilled_order.id} is not in fulfilled state."
    assert refund_response is False


def test_cybersource_order_no_transaction(fulfilled_order):
    """
    Test that refund_order returns False when there is no transaction against a fulfilled order
    Ideally, there should be a payment type transaction for a fulfilled order
    """

    fulfilled_order = OrderFactory.create(state=Order.STATE.FULFILLED)
    refund_response = refund_order(order_id=fulfilled_order.id)
    assert f"There is no associated transaction against order_id {fulfilled_order.id}."
    assert refund_response is False


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
        "refundAmountDetails": {"refundAmount": float(fulfilled_transaction.amount)}
    }
    sample_response = ProcessorResponse(
        state=order_state,
        response_data=sample_response_data,
        transaction_id="1234",
        message="",
        response_code="",
    )
    unenroll_task_mock = mocker.patch(
        "ecommerce.tasks.perform_unenrollment_from_order.delay"
    )

    mocker.patch(
        "mitol.payment_gateway.api.PaymentGateway.start_refund",
        return_value=sample_response,
    )
    refund_success = refund_order(
        order_id=fulfilled_transaction.order.id, unenroll=unenroll
    )

    if order_state == ProcessorResponse.STATE_DUPLICATE:
        assert f"Duplicate refund request for order_id {fulfilled_transaction.order.id}"

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
        unenroll_task_mock.assert_called_once_with(fulfilled_transaction.order.id)
    else:
        assert not unenroll_task_mock.called

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
    unenroll_task_mock = mocker.patch(
        "ecommerce.tasks.perform_unenrollment_from_order.delay"
    )

    with pytest.raises(ApiException):
        refund_response = refund_order(order_id=fulfilled_transaction.order.id)
        assert refund_response is False
    assert (
        Transaction.objects.filter(
            order=fulfilled_transaction.order.id,
            transaction_type=TRANSACTION_TYPE_REFUND,
        ).count()
        == 0
    )
    # Unenrollment task should not run when API fails
    assert not unenroll_task_mock.called


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


def test_process_cybersource_payment_response(rf, mocker, user_client, user, products):
    """Test that ensures the response from Cybersource for an ACCEPTed payment updates the orders state"""

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
