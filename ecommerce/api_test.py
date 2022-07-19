"""Tests for Ecommerce api"""

import pytest
import reversion
from reversion.models import Version
from courses.factories import CourseRunEnrollmentFactory
from ecommerce.api import refund_order, unenroll_learner_from_order
from ecommerce.models import FulfilledOrder, Order, Transaction
from ecommerce.factories import (
    OrderFactory,
    TransactionFactory,
    ProductFactory,
    LineFactory,
)
from ecommerce.constants import (
    TRANSACTION_TYPES,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
)
from mitol.payment_gateway.api import ProcessorResponse
from CyberSource.rest import ApiException

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


def test_cybersource_refund_no_order():
    """Tests that refund_order throws FulfilledOrder.DoesNotExist exception when the order doesn't exist"""

    with pytest.raises(FulfilledOrder.DoesNotExist):
        refund_order(order_id=1)  # Caling refund with random Id


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
