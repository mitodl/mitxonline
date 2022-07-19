import pytest
import reversion

from ecommerce.serializers_test import create_order_receipt
from ecommerce.factories import ProductFactory
from ecommerce.tasks import perform_unenrollment_from_order


@pytest.fixture()
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


def test_delayed_order_receipt_sends_email(mocker, user, products, user_client):
    """
    Tests that the Order model is properly calling the send email receipt task
    rather than calling the mail_api version directly. The create_order_receipt
    function should create a basket and process the order through to the point
    where the Order model itself will send the receipt email.
    """

    mock_send_ecommerce_order_receipt = mocker.patch(
        "ecommerce.mail_api.send_ecommerce_order_receipt"
    )

    create_order_receipt(mocker, user, products, user_client)

    mock_send_ecommerce_order_receipt.assert_called()


@pytest.mark.django_db
def test_delayed_unenrollment_unenrolls_user(mocker, user):
    """
    Test that unenroll task properly calls the unenrollment functionality against an order
    """

    unenroll_learner_mock = mocker.patch("ecommerce.api.unenroll_learner_from_order")
    perform_unenrollment_from_order.delay(order_id=1)
    unenroll_learner_mock.assert_called()
