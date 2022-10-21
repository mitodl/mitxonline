"""
Management command to create verified enrollment for a course run for the given User

Check the usages of this command below:

**Create verified enrollment**

1. Create verified enrollment for user
./manage.py create_verified_enrollment -—user=<username or email> -—run=<course_run_courseware_id> -code=<enrollment_code or discount_code>

**Keep failed enrollments**

4. Keep failed enrollments
./manage.py create_verified_enrollment -—user=<username or email> -—run=<course_run_courseware_id> -code=<enrollment_code or discount_code> -k or --keep-failed-enrollments
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.api import create_run_enrollments
from courses.models import CourseRun, PaidCourseRun
from ecommerce.api import fulfill_completed_order
from ecommerce.discounts import DiscountType
from ecommerce.models import Order, PendingOrder, Product, Discount
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
        super().add_arguments(parser)

    def handle(self, *args, **options):
        """Handle command execution"""
        user = fetch_user(options["user"])

        run = CourseRun.objects.filter(courseware_id=options["run"]).first()
        if run is None:
            raise CommandError(
                "Could not find course run with courseware_id={}".format(options["run"])
            )

        product = Product.objects.filter(
            object_id=run.id, content_type=ContentType.objects.get_for_model(CourseRun)
        ).first()
        if product is None:
            raise CommandError(
                "No product found for that course with courseware_id={}".format(
                    options["run"]
                )
            )

        if run.course.is_country_blocked(user):
            raise CommandError(
                "Enrollment is blocked of this course with courseware_id={} for user {}".format(
                    options["run"], options["user"]
                )
            )

        # PaidCourseRun should only contain fulfilled or review orders
        # but in order to avoid false positive passing in order__state__in here
        paid_course_run = PaidCourseRun.objects.filter(
            user=user,
            course_run=run,
            order__state__in=[Order.STATE.FULFILLED, Order.STATE.REVIEW],
        ).first()
        if paid_course_run:
            raise CommandError(
                "User {} already enrolled in this course with courseware_id={}\nEnrollment order:{}".format(
                    options["user"], options["run"], paid_course_run.order
                )
            )

        if not run.is_upgradable:
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
            discount.products.filter(product=product).exists()
        ):
            raise CommandError(
                "That enrollment code {} is invalid for course with courseware_id={}".format(
                    options["code"], options["run"]
                )
            )

        if not discount.check_validity(user):
            raise CommandError(
                "That enrollment code {} for course with courseware_id={} is invalid for user {}".format(
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
