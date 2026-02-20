"""Tests for ecommerce admin views"""

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from ecommerce.factories import OrderFactory
from ecommerce.models import OrderStatus

pytestmark = [pytest.mark.django_db]


def _login_admin(client, admin_user):
    """Log in the admin user into the Django test client."""

    client.force_login(admin_user)
    return client


def test_admin_refund_order_get_success(client, admin_user):
    """GET should render the refund confirmation page for a fulfilled order."""

    _login_admin(client, admin_user)
    order = OrderFactory.create(state=OrderStatus.FULFILLED)

    response = client.get(f"{reverse('refund-order')}?order={order.id}")

    assert response.status_code == 200
    assert response.context["order"].id == order.id

    refund_form = response.context["refund_form"]
    assert refund_form.initial["_selected_action"] == order.id
    assert float(refund_form.initial["refund_amount"]) == float(order.total_price_paid)
    assert response.context["form_valid"] is True
    assert response.context["errors"] == {}


def test_admin_refund_order_get_not_found(client, admin_user):
    """GET with a non-existing order should redirect with an error message."""

    _login_admin(client, admin_user)
    missing_order_id = 999999

    response = client.get(f"{reverse('refund-order')}?order={missing_order_id}")

    assert response.status_code == 302
    assert response.url == reverse("admin:ecommerce_fulfilledorder_changelist")

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert f"Order {missing_order_id} could not be found - is it Fulfilled?" == str(
        messages[0].message
    )


def test_admin_refund_order_get_not_fulfilled(client, admin_user):
    """GET with a non-fulfilled order should behave like missing fulfilled order."""

    _login_admin(client, admin_user)
    order = OrderFactory.create(state=OrderStatus.PENDING)

    response = client.get(f"{reverse('refund-order')}?order={order.id}")

    assert response.status_code == 302
    assert response.url == reverse("admin:ecommerce_fulfilledorder_changelist")

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert f"Order {order.id} could not be found - is it Fulfilled?" == str(
        messages[0].message
    )


@pytest.mark.parametrize(
    "perform_unenrolls, expected_message_suffix",
    [
        (False, "refunded."),
        (True, "refunded and unenrollment is in progress."),
    ],
)
def test_admin_refund_order_post_success(
    client, admin_user, mocker, perform_unenrolls, expected_message_suffix
):
    """POST with valid data should call refund_order and redirect to refunded order admin."""

    _login_admin(client, admin_user)
    order = OrderFactory.create(state=OrderStatus.FULFILLED)

    mock_refund_order = mocker.patch(
        "ecommerce.admin.refund_order", return_value=(True, None)
    )

    post_data = {
        "order": str(order.id),
        "_selected_action": str(order.id),
        "refund_reason": "Test refund",
        "refund_amount": "10.00",
    }
    if perform_unenrolls:
        post_data["perform_unenrolls"] = "on"

    response = client.post(reverse("refund-order"), data=post_data)

    assert response.status_code == 302
    assert response.url == reverse(
        "admin:ecommerce_refundedorder_change", args=(order.id,)
    )

    mock_refund_order.assert_called_once()
    kwargs = mock_refund_order.call_args.kwargs
    assert kwargs["order_id"] == order.id
    assert kwargs["refund_reason"] == "Test refund"
    assert kwargs["unenroll"] is perform_unenrolls

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert (
        str(messages[0].message)
        == f"Order {order.reference_number} {expected_message_suffix}"
    )


def test_admin_refund_order_post_refund_failed(client, admin_user, mocker):
    """If refund_order returns False, an error message is shown and redirect occurs."""

    _login_admin(client, admin_user)
    order = OrderFactory.create(state=OrderStatus.FULFILLED)

    mocker.patch("ecommerce.admin.refund_order", return_value=(False, "error"))

    post_data = {
        "order": str(order.id),
        "_selected_action": str(order.id),
        "refund_reason": "Test refund",
        "refund_amount": "10.00",
    }

    response = client.post(reverse("refund-order"), data=post_data)

    assert response.status_code == 302
    assert response.url == reverse(
        "admin:ecommerce_refundedorder_change", args=(order.id,)
    )

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert str(messages[0].message) == f"Order {order.reference_number} refund failed."


def test_admin_refund_order_post_invalid_form(client, admin_user, mocker):
    """Invalid form data should re-render the page with errors and not call refund_order."""

    _login_admin(client, admin_user)
    order = OrderFactory.create(state=OrderStatus.FULFILLED)

    mock_refund_order = mocker.patch("ecommerce.admin.refund_order")

    post_data = {
        "order": str(order.id),
        "_selected_action": str(order.id),
    }

    response = client.post(reverse("refund-order"), data=post_data)

    assert response.status_code == 200
    mock_refund_order.assert_not_called()

    assert response.context["form_valid"] is False
    assert "refund_reason" in response.context["errors"]
    assert "refund_amount" in response.context["errors"]


def test_admin_refund_order_post_not_implemented(client, admin_user, mocker):
    """NotImplementedError from refund_order should redirect with a specific error message."""

    _login_admin(client, admin_user)
    order = OrderFactory.create(state=OrderStatus.FULFILLED)

    mocker.patch("ecommerce.admin.refund_order", side_effect=NotImplementedError)

    post_data = {
        "order": str(order.id),
        "_selected_action": str(order.id),
        "refund_reason": "Test refund",
        "refund_amount": "10.00",
    }

    response = client.post(reverse("refund-order"), data=post_data)

    assert response.status_code == 302
    assert response.url == reverse("admin:ecommerce_refundedorder_changelist")

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert str(messages[0].message) == f"Order {order.id} can't be refunded."


def test_admin_refund_order_post_order_not_found(client, admin_user):
    """Missing order on POST should redirect to fulfilled orders changelist with an error."""

    _login_admin(client, admin_user)
    missing_order_id = 999999

    post_data = {
        "order": str(missing_order_id),
        "_selected_action": str(missing_order_id),
        "refund_reason": "Test refund",
        "refund_amount": "10.00",
    }

    response = client.post(reverse("refund-order"), data=post_data)

    assert response.status_code == 302
    assert response.url == reverse("admin:ecommerce_fulfilledorder_changelist")

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert (
        str(messages[0].message)
        == f"Order {missing_order_id} could not be found - is it Fulfilled?"
    )
