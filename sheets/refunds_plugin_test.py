"""Tests for the refund sheet plugin"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from mitol.google_sheets.utils import ResultType

from courses.factories import CourseRunFactory, ProgramFactory
from ecommerce.factories import make_purchase
from ecommerce.models import OrderStatus
from sheets.refunds_plugin import RefundPlugin
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_refund_order(mocker):
    """Patch refund_order so no payment gateway is called"""
    return mocker.patch("sheets.refunds_plugin.refund_order", return_value=(True, ""))


def _row(order_ref_num, learner_email, product_id):
    """The refund sheet row fields the plugin reads"""
    return SimpleNamespace(
        order_ref_num=order_ref_num,
        learner_email=learner_email,
        product_id=product_id,
    )


def _process(row):
    return RefundPlugin().refunds_process_request(refund_request_row=row)


@pytest.mark.parametrize("product_id_kind", ["product_id", "readable_id"])
@pytest.mark.parametrize("is_program", [False, True])
def test_refund_row_matching_order_is_refunded(
    mock_refund_order, product_id_kind, is_program
):
    """
    A row whose learner and product match its order is refunded, with the
    product given as either the product id or the run/program readable id.
    The email match ignores case.
    """
    user = UserFactory.create(email="Learner@Example.com")
    purchasable = ProgramFactory.create() if is_program else CourseRunFactory.create()
    line = make_purchase(user, purchasable, Decimal("100.00"))
    order = line.order
    product_id = (
        line.product_version.object_id
        if product_id_kind == "product_id"
        else (purchasable.readable_id if is_program else purchasable.courseware_id)
    )

    result = _process(_row(order.reference_number, "learner@example.com", product_id))

    assert result.result_type == ResultType.PROCESSED
    mock_refund_order.assert_called_once_with(
        reference_number=order.reference_number, unenroll=True
    )


@pytest.mark.parametrize(
    "mismatch, expected_message",  # noqa: PT006
    [
        ("unknown_order", "No fulfilled order with reference number"),
        ("unfulfilled_order", "No fulfilled order with reference number"),
        ("other_learner", "does not match the purchaser"),
        ("blank_learner", "does not match the purchaser"),
        ("other_product", "is not in order"),
        ("blank_product", "is not in order"),
    ],
)
def test_refund_row_mismatch_fails_without_refunding(
    mock_refund_order, mismatch, expected_message
):
    """Any mismatch between the row and its order fails the row and refunds nothing"""
    user = UserFactory.create()
    run = CourseRunFactory.create()
    line = make_purchase(
        user,
        run,
        Decimal("100.00"),
        state=(
            OrderStatus.REFUNDED
            if mismatch == "unfulfilled_order"
            else OrderStatus.FULFILLED
        ),
    )
    other_run = CourseRunFactory.create()

    row = _row(
        "not-a-real-order"
        if mismatch == "unknown_order"
        else line.order.reference_number,
        {
            "other_learner": UserFactory.create().email,
            "blank_learner": "",
        }.get(mismatch, user.email),
        {
            "other_product": other_run.courseware_id,
            "blank_product": "",
        }.get(mismatch, run.courseware_id),
    )

    result = _process(row)

    assert result.result_type == ResultType.FAILED
    assert expected_message in result.message
    mock_refund_order.assert_not_called()


def test_refund_row_failed_refund_fails_the_row(mock_refund_order):
    """A matching row whose refund fails is reported as failed with the reason"""
    user = UserFactory.create()
    run = CourseRunFactory.create()
    line = make_purchase(user, run, Decimal("100.00"))
    mock_refund_order.return_value = (False, "gateway said no")

    result = _process(_row(line.order.reference_number, user.email, run.courseware_id))

    assert result.result_type == ResultType.FAILED
    assert result.message == "gateway said no"
