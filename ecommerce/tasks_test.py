import pytest
import reversion
import stripe
from celery.exceptions import Retry

from ecommerce.factories import OrderFactory, ProductFactory
from ecommerce.models import OrderStatus
from ecommerce.serializers.serializers_test import create_order_receipt
from ecommerce.tasks import (
    expire_cancelled_stripe_checkout,
    perform_cull_anonymous_baskets,
    perform_cull_stale_pending_orders,
    perform_downgrade_from_order,
    perform_unenrollment_from_order,
)


@pytest.fixture
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


def test_perform_cull_anonymous_baskets_calls_api(mocker):
    """The task should just delegate to the api function"""
    mock_cull = mocker.patch("ecommerce.api.cull_anonymous_baskets")

    perform_cull_anonymous_baskets()

    mock_cull.assert_called_once()


def test_perform_cull_stale_pending_orders_calls_api(mocker):
    """The task should just delegate to the api function"""
    mock_cull = mocker.patch("ecommerce.api.cull_stale_pending_orders")

    perform_cull_stale_pending_orders()

    mock_cull.assert_called_once()


@pytest.mark.skip_nplusone_check
def test_delayed_order_receipt_sends_email(  # noqa: PLR0913
    settings, mocker, user, products, user_client, django_capture_on_commit_callbacks
):
    """
    Tests that the Order model is properly calling the send email receipt task
    rather than calling the mail_api version directly. The create_order_receipt
    function should create a basket and process the order through to the point
    where the Order model itself will send the receipt email.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
    mock_send_ecommerce_order_receipt = mocker.patch(
        "ecommerce.mail_api.send_ecommerce_order_receipt"
    )

    with django_capture_on_commit_callbacks(execute=True):
        create_order_receipt(mocker, user, products, user_client)

    mock_send_ecommerce_order_receipt.assert_called()


@pytest.mark.skip_nplusone_check
def test_delayed_order_refund_sends_email(  # noqa: PLR0913
    settings, mocker, user, products, user_client, django_capture_on_commit_callbacks
):
    """
    Tests that the Order model is properly calling the order refund email task
    rather than calling the mail_api version directly. The create_order_receipt
    function creates a fulfilled order, then we refund it and make sure the
    right task got called.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
    mock_send_refund_email = mocker.patch(
        "ecommerce.mail_api.send_ecommerce_refund_message"
    )

    order = create_order_receipt(mocker, user, products, user_client)

    transaction_data = {"id": "refunded-transaction"}
    refund_amount = order.total_price_paid / 2
    order_flow = order.get_object_flow()
    with django_capture_on_commit_callbacks(execute=True):
        order_flow.refund(
            api_response_data=transaction_data,
            amount=refund_amount,
            reason="testing",
        )

    mock_send_refund_email.assert_called()


@pytest.mark.django_db
def test_delayed_unenrollment_unenrolls_user(mocker, user):
    """
    Test that unenroll task properly calls the unenrollment functionality against an order
    """

    unenroll_learner_mock = mocker.patch("ecommerce.api.unenroll_learner_from_order")
    perform_unenrollment_from_order.delay(order_id=1)
    unenroll_learner_mock.assert_called()


@pytest.mark.django_db
def test_delayed_downgrade_user(mocker, user):
    """
    Test that unenroll task properly calls the unenrollment functionality against an order
    """

    downgrade_learner_mock = mocker.patch(
        "ecommerce.api.downgrade_enrollments_from_order"
    )
    perform_downgrade_from_order.delay(order_id=1)
    downgrade_learner_mock.assert_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state", [OrderStatus.PENDING, OrderStatus.CANCELED, OrderStatus.FULFILLED]
)
def test_expire_cancelled_stripe_checkout(mocker, state):
    """
    The task expires the session of an order that's pending, or that staff
    cancelled, but leaves a paid one alone.
    """
    mock_expire = mocker.patch("ecommerce.api.expire_stripe_checkout_session")
    order = OrderFactory.create(state=state)

    expire_cancelled_stripe_checkout(order.id)

    if state != OrderStatus.FULFILLED:
        mock_expire.assert_called_once_with(order)
    else:
        mock_expire.assert_not_called()


@pytest.mark.django_db
def test_expire_cancelled_stripe_checkout_retries(mocker):
    """A Stripe error retries the task, so the cancelled page doesn't stay payable."""
    mock_expire = mocker.patch(
        "ecommerce.api.expire_stripe_checkout_session",
        side_effect=stripe.APIConnectionError("Stripe is down"),
    )
    order = OrderFactory.create(state=OrderStatus.PENDING)

    with pytest.raises(Retry):
        expire_cancelled_stripe_checkout.apply(args=[order.id])

    mock_expire.assert_called_once_with(order)


@pytest.mark.django_db
def test_expire_cancelled_stripe_checkout_no_retry_on_bad_request(mocker):
    """A Stripe error that won't go away on retry isn't retried."""
    mocker.patch(
        "ecommerce.api.expire_stripe_checkout_session",
        side_effect=stripe.AuthenticationError("bad key"),
    )
    order = OrderFactory.create(state=OrderStatus.PENDING)

    with pytest.raises(stripe.AuthenticationError):
        expire_cancelled_stripe_checkout.apply(args=[order.id])


def test_expire_cancelled_stripe_checkout_outlasts_session():
    """Retries keep going past the 24-hour session lifetime."""
    task = expire_cancelled_stripe_checkout

    assert task.max_retries * task.retry_backoff_max >= 24 * 60 * 60
