from mitol.google_sheets_refunds.hooks import hookimpl, RefundResult
from mitol.google_sheets_refunds.utils import RefundRequestRow
from mitol.google_sheets_deferrals.hooks import hookimpl, DeferralResult
from mitol.google_sheets_deferrals.utils import DeferralRequestRow
from mitol.google_sheets.utils import ResultType

from ecommerce.api import refund_order
from courses.api import defer_enrollment
from users.api import fetch_user


class RefundPlugin:
    @hookimpl
    def refunds_process_request(
        self, refund_request_row: RefundRequestRow
    ) -> RefundResult:

        refund_api_success = refund_order(
            reference_number=refund_request_row.order_ref_num, unenroll=True
        )
        if refund_api_success:
            return RefundResult(ResultType.PROCESSED)

        return RefundResult(ResultType.FAILED)


class DeferralPlugin:
    @hookimpl
    def deferrals_process_request(
        self, deferral_request_row: DeferralRequestRow
    ) -> DeferralResult:
        user = fetch_user(deferral_request_row.learner_email)
        from_courseware_id = deferral_request_row.from_courseware_id
        to_courseware_id = deferral_request_row.to_courseware_id

        deferral_api_success = defer_enrollment(
            user,
            from_courseware_id,
            to_courseware_id,
        )
        if deferral_api_success:
            return DeferralResult(ResultType.PROCESSED)

        return DeferralResult(ResultType.FAILED)
