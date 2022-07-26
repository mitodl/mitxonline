from mitol.google_sheets_refunds.hooks import hookimpl, RefundResult
from mitol.google_sheets_refunds.utils import RefundRequestRow
from mitol.google_sheets.utils import ResultType

from ecommerce.api import refund_order


class RefundPlugin:
    @hookimpl
    def refunds_process_request(
        self, refund_request_row: RefundRequestRow
    ) -> RefundResult:

        refund_api_success = refund_order(
            order_id=refund_request_row.order_id,
            unenroll=True
        )
        if refund_api_success:
            return RefundResult(ResultType.PROCESSED.value)

        return RefundResult(ResultType.FAILED.value)
