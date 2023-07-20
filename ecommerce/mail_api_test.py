import pytest
import reversion

from decimal import Decimal

from ecommerce.serializers_test import create_order_receipt
from ecommerce.factories import ProductFactory
from ecommerce.tasks import send_ecommerce_order_receipt
from ecommerce.views_test import payment_gateway_settings

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


def test_mail_api_task_called(
    settings, mocker, user, products, user_client, django_capture_on_commit_callbacks
):
    """
    Tests that the Order model is properly calling the send email receipt task
    rather than calling the mail_api version directly. The create_order_receipt
    function should create a basket and process the order through to the point
    where the Order model itself will send the receipt email.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    mock_delayed_send_ecommerce_order_receipt = mocker.patch(
        "ecommerce.tasks.send_ecommerce_order_receipt.delay"
    )

    with django_capture_on_commit_callbacks(execute=True):
        order = create_order_receipt(mocker, user, products, user_client)

    mock_delayed_send_ecommerce_order_receipt.assert_called()
    assert mock_delayed_send_ecommerce_order_receipt.call_args[0][0] == order.id


def test_mail_api_receipt_generation(
    settings, mocker, user, products, user_client, django_capture_on_commit_callbacks
):
    """
    Tests email generation. Mocks actual message sending and then looks for some
    key data in the rendered template body (name from legal address, order ID,
    and line item unit price).
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    mock_send_message = mocker.patch("mitol.mail.api.send_message")

    with django_capture_on_commit_callbacks(execute=True):
        order = create_order_receipt(mocker, user, products, user_client)

    mock_send_message.assert_called()

    rendered_template = mock_send_message.call_args[0][0]

    assert (
        "{} {}".format(
            order.purchaser.legal_address.first_name,
            order.purchaser.legal_address.last_name,
        )
        in rendered_template.body
    )
    assert order.reference_number in rendered_template.body

    lines = order.lines.all()
    assert str(lines[0].unit_price) in rendered_template.body


def test_mail_api_refund_email_generation(settings, mocker, user, products, user_client):
    """
    Tests email generation for the refund message. Generates a fulfilled order,
    then attemps to refund it after mocking the mail sender.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
    order = create_order_receipt(mocker, user, products, user_client)

    mock_send_message = mocker.patch("mitol.mail.api.send_message")

    transaction_data = {"id": "refunded-transaction"}
    refund_amount = order.total_price_paid / 2

    transaction = order.refund(
        api_response_data=transaction_data, amount=refund_amount, reason="testing"
    )

    mock_send_message.assert_called()

    rendered_template = mock_send_message.call_args[0][0]

    assert (
        "{} {}".format(
            order.purchaser.legal_address.first_name,
            order.purchaser.legal_address.last_name,
            order.purchased_runs[0].course_number,
        )
        in rendered_template.body
    )
    assert order.reference_number in rendered_template.body
    assert str(refund_amount.quantize(Decimal("0.01"))) in rendered_template.body
