from mitol.google_sheets.utils import ResultType
from mitol.google_sheets_refunds.hooks import RefundResult, hookimpl
from mitol.google_sheets_refunds.utils import RefundRequestRow

from ecommerce.api import refund_order
from ecommerce.models import FulfilledOrder, OrderStatus


def _line_product_ids(line):
    """
    The values a refund row's product id can name a line by: the product's id
    or the readable id of the course run/program it sells.
    """
    purchased_object = line.purchased_object
    return {
        str(line.product_version.object_id),
        getattr(purchased_object, "courseware_id", None),
        getattr(purchased_object, "readable_id", None),
    } - {None}


def _refund_row_mismatch(refund_request_row):
    """
    Check that the row's order exists and matches the row's learner and
    product. Return a reason to fail the row, or None if it matches.
    """
    reference_number = refund_request_row.order_ref_num
    # FulfilledOrder is a plain proxy - its manager doesn't filter on state.
    order = (
        FulfilledOrder.objects.filter(
            reference_number=reference_number, state=OrderStatus.FULFILLED
        )
        .select_related("purchaser")
        .prefetch_related("lines__product_version", "lines__purchased_object")
        .first()
    )
    if order is None:
        return f"No fulfilled order with reference number {reference_number}"

    learner_email = (refund_request_row.learner_email or "").strip()
    if learner_email.casefold() != order.purchaser.email.casefold():
        return (
            f"Learner email {learner_email} does not match the purchaser of "
            f"order {reference_number}"
        )

    product_id = (refund_request_row.product_id or "").strip()
    if not any(product_id in _line_product_ids(line) for line in order.lines.all()):
        return f"Product {product_id} is not in order {reference_number}"

    return None


class RefundPlugin:
    @hookimpl
    def refunds_process_request(
        self, refund_request_row: RefundRequestRow
    ) -> RefundResult:
        # The row names the learner and product as well as the order; refund
        # only if all three agree, so a mistyped reference number can't refund
        # (and unenroll) someone else's order or the learner's other order.
        mismatch = _refund_row_mismatch(refund_request_row)
        if mismatch:
            return RefundResult(ResultType.FAILED, mismatch)

        refund_success, message = refund_order(
            reference_number=refund_request_row.order_ref_num, unenroll=True
        )
        if refund_success:
            return RefundResult(ResultType.PROCESSED)

        return RefundResult(ResultType.FAILED, message)
