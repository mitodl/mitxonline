from mitol.google_sheets.utils import ResultType
from mitol.google_sheets_refunds.hooks import RefundResult, hookimpl
from mitol.google_sheets_refunds.utils import RefundRequestRow

from ecommerce.api import refund_order


class RefundPlugin:
    @hookimpl
    def refunds_process_request(
        self, refund_request_row: RefundRequestRow
    ) -> RefundResult:
        refund_success, message = refund_order(
            reference_number=refund_request_row.order_ref_num, unenroll=True
        )
        if refund_success:
            return RefundResult(ResultType.PROCESSED)

        return RefundResult(ResultType.FAILED, message)
