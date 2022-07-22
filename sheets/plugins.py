from django.core.exceptions import ObjectDoesNotExist
from mitol.google_sheets_refunds.hooks import hookimpl, RefundResult
from mitol.google_sheets_refunds.utils import RefundRequestRow
from mitol.google_sheets.utils import ResultType

from courses.api import (
    is_program_text_id,
    deactivate_program_enrollment,
    deactivate_run_enrollment,
)
from courses.constants import ENROLL_CHANGE_STATUS_REFUNDED
from courses.models import ProgramEnrollment, CourseRunEnrollment
from ecommerce.models import Order
from users.models import User


class RefundPlugin:
    @staticmethod
    def get_order_objects(refund_req_row):
        """
        Fetches all of the database objects relevant to this refund request

        Args:
            refund_req_row (RefundRequestRow): An object representing a row in the spreadsheet

        Returns:
            (Order, ProgramEnrollment or CourseRunEnrollment): The order and enrollment associated
                with this refund request.
        """
        user = User.objects.get(email__iexact=refund_req_row.learner_email)
        order = Order.objects.get(id=refund_req_row.order_id, purchaser=user)
        if is_program_text_id(refund_req_row.product_id):
            enrollment = ProgramEnrollment.all_objects.get(
                order=order, program__readable_id=refund_req_row.product_id
            )
        else:
            enrollment = CourseRunEnrollment.all_objects.get(
                order=order, run__courseware_id=refund_req_row.product_id
            )
        return order, enrollment

    @staticmethod
    def reverse_order_and_enrollments(order, enrollment):
        """
        Sets the state of the given order and enrollment(s) to reflect that they have
        been refunded and are no longer active

        Args:
            order (Order):
            enrollment (ProgramEnrollment or CourseRunEnrollment):
        """
        if isinstance(enrollment, ProgramEnrollment):
            deactivated_enrollment, _ = deactivate_program_enrollment(
                enrollment, change_status=ENROLL_CHANGE_STATUS_REFUNDED
            )
        else:
            deactivated_enrollment = deactivate_run_enrollment(
                enrollment, change_status=ENROLL_CHANGE_STATUS_REFUNDED
            )
        # When #1838 is completed, this logic can be removed
        if deactivated_enrollment is None:
            raise Exception("Enrollment change failed in edX")
        order.status = Order.REFUNDED
        order.save_and_log(acting_user=None)

    @hookimpl
    def refunds_process_request(
        self, refund_request_row: RefundRequestRow
    ) -> RefundResult:

        try:
            order, enrollment = self.get_order_objects(refund_request_row)
        except ObjectDoesNotExist as exc:
            if isinstance(exc, User.DoesNotExist):
                message = "User with email '{}' not found".format(
                    refund_request_row.learner_email
                )
            elif isinstance(exc, Order.DoesNotExist):
                message = "Order with id {} and purchaser '{}' not found".format(
                    refund_request_row.order_id, refund_request_row.learner_email
                )
            elif isinstance(
                exc, (ProgramEnrollment.DoesNotExist, CourseRunEnrollment.DoesNotExist)
            ):
                message = "Program/Course run enrollment does not exist for product '{}' and order {}".format(
                    refund_request_row.product_id, refund_request_row.order_id
                )
            else:
                raise
            return ResultType.FAILED

        self.reverse_order_and_enrollments(order, enrollment)
        return ResultType.PROCESSED, None
