"""
Looks up a fulfilled order in the system, sets it to Refunded, and then adjusts
the enrollments accordingly.

- If --unenroll is specified, the learner will be unenrolled from the course run
  associated with the order.
- If --audit is specified, the learner will keep their unenrollments, but they
  will be set to "audit" instead of "verified".

This does not make any sort of call to CyberSource or any other payment gateway
to perform a refund - you're expected to have refunded the learner's money
manually already. (At time of writing, PayPal transactions can't be refunded
using the normal means, so they get refunded manually via CyberSource and then
this command comes in to clean up afterwards.)

"""

from django.core.management import BaseCommand
from django.core.management.base import CommandError

from courses.api import deactivate_run_enrollment
from courses.models import CourseRunEnrollment
from ecommerce.models import Order
from hubspot_sync.task_helpers import sync_hubspot_deal
from openedx.api import enroll_in_edx_course_runs


class Command(BaseCommand):
    """
    Looks up a fulfilled order in the system, sets it to Refunded, and then adjusts the enrollments accordingly.
    """

    help = "Looks up a fulfilled order in the system, sets it to Refunded, and then adjusts the enrollments accordingly."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "order", type=str, help="The order reference number to retrieve."
        )
        parser.add_argument(
            "--unenroll",
            action="store_true",
            help="Completely unenroll the learner from the course(s).",
        )
        parser.add_argument(
            "--audit",
            action="store_true",
            help="Set the learner's enrollments to audit.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        if ("audit" not in kwargs or not kwargs["audit"]) and (
            "unenroll" not in kwargs or not kwargs["unenroll"]
        ):
            raise CommandError("Please specify an action to take on the enrollment.")  # noqa: EM101

        try:
            order = Order.objects.filter(
                state=Order.STATE.FULFILLED, reference_number=kwargs["order"]
            ).get()
        except:  # noqa: E722
            raise CommandError("Couldn't find that order, or the order was ambiguous.")  # noqa: B904, EM101

        order.state = Order.STATE.REFUNDED
        order.save()
        sync_hubspot_deal(order)

        run_enrollments = (
            CourseRunEnrollment.objects.filter(user=order.purchaser)
            .filter(run__in=order.purchased_runs)
            .all()
        )

        for enrollment in run_enrollments:
            if kwargs.get("unenroll"):
                self.stdout.write(
                    f"Unenrolling {order.purchaser.username} in {enrollment.run}"
                )
                deactivate_run_enrollment(enrollment, "refunded", True)  # noqa: FBT003
            else:
                self.stdout.write(
                    f"Changing enrollment for {order.purchaser.username} in {enrollment.run} to 'audit'"
                )

                enrollment.update_mode_and_save("audit")

                enroll_in_edx_course_runs(
                    order.purchaser, [enrollment.run], mode="audit"
                )

        self.stdout.write(
            self.style.SUCCESS(f"Updated order {order.reference_number}.")
        )
