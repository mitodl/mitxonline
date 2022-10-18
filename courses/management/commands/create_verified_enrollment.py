"""Management command to change enrollment status"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.api import create_run_enrollments
from courses.models import CourseRun, PaidCourseRun
from ecommerce.api import fulfill_completed_order
from ecommerce.discounts import DiscountType
from ecommerce.models import Order, PendingOrder, Product, Discount, DiscountProduct
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """creates an enrollment for a course run"""

    help = "Creates an enrollment for a course run"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the User",
            required=True,
        )
        parser.add_argument(
            "--run",
            type=str,
            help="The 'courseware_id' value for the CourseRun",
            required=True,
        )
        parser.add_argument(
            "--code", type=str, help="The enrollment code for the course", required=True
        )
        parser.add_argument(
            "-k",
            "--keep-failed-enrollments",
            action="store_true",
            dest="keep_failed_enrollments",
            help="If provided, enrollment records will be kept even if edX enrollment fails",
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            dest="force",
            help="If provided, Enroll user in expired courses",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):
        """Handle command execution"""
        user = fetch_user(options["user"])

        run = CourseRun.objects.filter(courseware_id=options["run"]).first()
        if run is None:
            raise CommandError(
                "Could not find course run with courseware_id={}".format(options["run"])
            )

        product = Product.objects.filter(object_id=run.id).first()
        if product is None:
            raise CommandError(
                "No product found for that course with courseware_id={}".format(
                    options["run"]
                )
            )

        purchased_object = product.purchasable_object

        if purchased_object.course.is_country_blocked(user):
            raise CommandError(
                "Enrollment is blocked of this course with courseware_id={} for user {}".format(
                    options["run"], options["user"]
                )
            )

        if isinstance(purchased_object, CourseRun):
            # PaidCourseRun should only contain fulfilled or review orders
            # but in order to avoid false positive passing in order__state__in here
            if PaidCourseRun.objects.filter(
                user=user,
                course_run=purchased_object,
                order__state__in=[Order.STATE.FULFILLED, Order.STATE.REVIEW],
            ).exists():
                raise CommandError(
                    "User {} already enrolled in this course with courseware_id={}".format(
                        options["user"], options["run"]
                    )
                )

        if (
            not options["force"]
            and isinstance(purchased_object, CourseRun)
            and not purchased_object.is_upgradable
        ):
            raise CommandError(
                "The course with courseware_id={} is not upgradeable or the upgrade deadline has been passed".format(
                    options["run"]
                )
            )

        discount = Discount.objects.filter(
            for_flexible_pricing=False, discount_code=options["code"]
        ).first()
        if not discount:
            raise CommandError(
                "That enrollment code {} does not exist".format(options["code"])
            )

        if discount.products.exists() and not (
            DiscountProduct.objects.filter(product=product, discount=discount).exists()
        ):
            raise CommandError(
                "That enrollment code {} is not valid for course with courseware_id={}".format(
                    options["code"], options["run"]
                )
            )

        if not discount.check_validity(user):
            raise CommandError(
                "That enrollment code {} for course with courseware_id={} is not valid for user {}".format(
                    options["code"], options["run"], options["user"]
                )
            )

        discounted_price = DiscountType.get_discounted_price([discount], product)

        if discounted_price > 0:
            raise CommandError("Discount code is not 100% off")

        with transaction.atomic():
            successful_enrollments, edx_request_success = create_run_enrollments(
                user,
                [run],
                keep_failed_enrollments=options["keep_failed_enrollments"],
                mode=EDX_ENROLLMENT_VERIFIED_MODE,
            )
            if not successful_enrollments:
                raise CommandError("Failed to create the enrollment record")
            order = PendingOrder.create_from_product(product, user, discount)
            fulfill_completed_order(
                order,
                {"amount": 0, "data": {"reason": "No payment required"}},
                already_enrolled=True,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Enrollment created for user {} in {} (edX enrollment success: {})".format(
                    user, options["run"], edx_request_success
                )
            )
        )
