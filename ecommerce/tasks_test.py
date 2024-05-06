import pytest
import reversion

from ecommerce.factories import ProductFactory
from ecommerce.serializers_test import create_order_receipt
from ecommerce.tasks import (
    perform_downgrade_from_order,
    perform_unenrollment_from_order,
)


@pytest.fixture
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


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


def test_delayed_order_refund_sends_email(
    settings, mocker, user, products, user_client
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

    order.refund(
        api_response_data=transaction_data, amount=refund_amount, reason="testing"
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

    downgrade_learner_mock = mocker.patch("ecommerce.api.downgrade_learner_from_order")
    perform_downgrade_from_order.delay(order_id=1)
    downgrade_learner_mock.assert_called()
