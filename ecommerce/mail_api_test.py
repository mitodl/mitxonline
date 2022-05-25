import pytest
import reversion

from ecommerce.serializers_test import create_order_receipt
from ecommerce.factories import ProductFactory
from ecommerce.tasks import send_ecommerce_order_receipt
from ecommerce.views_test import payment_gateway_settings

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def products():
    with reversion.create_revision():
        return ProductFactory.create_batch(5)


def test_mail_api_task_called(mocker, user, products, user_client):
    """
    Tests that the Order model is properly calling the send email receipt task
    rather than calling the mail_api version directly. The create_order_receipt
    function should create a basket and process the order through to the point
    where the Order model itself will send the receipt email.
    """
    mock_delayed_send_ecommerce_order_receipt = mocker.patch(
        "ecommerce.tasks.send_ecommerce_order_receipt.delay"
    )

    order = create_order_receipt(mocker, user, products, user_client)

    mock_delayed_send_ecommerce_order_receipt.assert_called()
    assert mock_delayed_send_ecommerce_order_receipt.call_args[0][0] == order.id


def test_mail_api_receipt_generation(mocker, user, products, user_client):
    """
    Tests email generation. Mocks actual message sending and then looks for some
    key data in the rendered template body (name from legal address, order ID,
    and line item unit price).
    """
    mock_send_message = mocker.patch("mitol.mail.api.send_message")

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
