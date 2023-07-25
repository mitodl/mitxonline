from mitol.google_sheets_deferrals.hooks import hookimpl, DeferralResult
from mitol.google_sheets_deferrals.utils import DeferralRequestRow
from mitol.google_sheets.utils import ResultType

from courses.api import defer_enrollment
from users.api import fetch_user


class DeferralPlugin:
    @hookimpl
    def deferrals_process_request(
        self, deferral_request_row: DeferralRequestRow
    ) -> DeferralResult:
        user = fetch_user(deferral_request_row.learner_email)
        from_courseware_id = deferral_request_row.from_courseware_id
        to_courseware_id = deferral_request_row.to_courseware_id

        from_enrollment, to_enrollment = defer_enrollment(
            user,
            from_courseware_id,
            to_courseware_id,
            force=True,
        )
        if to_courseware_id and not to_enrollment:
            message = "Failed to create/update the target enrollment ({})".format(
                    to_courseware_id
                )
            return DeferralResult(ResultType.FAILED, message)
        return DeferralResult(ResultType.PROCESSED)
