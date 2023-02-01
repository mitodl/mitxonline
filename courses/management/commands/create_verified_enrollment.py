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
from ecommerce.constants import ZERO_PAYMENT_DATA, PAYMENT_TYPE_FINANCIAL_ASSISTANCE
from ecommerce.discounts import DiscountType
from ecommerce.models import PendingOrder, Product, Discount
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """creates an enrollment for a course run"""

    help = "Creates a verified enrollment for a course run"

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
            "-f",
            "--force",
            action="store_true",
            dest="force",
            help="If provided, user will be enrolled even if edX enrollment end date is expired",
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
        force_enrollment = options["force"]

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
        if PaidCourseRun.fulfilled_paid_course_run_exists(user, run):
            raise CommandError(
                "User {} already enrolled in this course with courseware_id={}".format(
                    options["user"], options["run"]
                )
            )

        if not force_enrollment and not run.is_upgradable:
            raise CommandError(
                "The course with courseware_id={} is not upgradeable or the upgrade deadline has been passed".format(
                    options["run"]
                )
            )

        discount = Discount.objects.filter(
            discount_code=options["code"]
        ).exclude(
            payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE
        ).first()
        if not discount:
            raise CommandError(
                "That enrollment code {} does not exist".format(options["code"])
            )

        if not discount.check_validity_with_products([product]):
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
            raise CommandError("Enrollment code is not 100% off")

        if run.course.is_country_blocked(user):
            raise CommandError(
                "Enrollment is blocked of this course with courseware_id={} for user {}".format(
                    options["run"], options["user"]
                )
            )

        with transaction.atomic():
            successful_enrollments, edx_request_success = create_run_enrollments(
                user,
                [run],
                keep_failed_enrollments=options["keep_failed_enrollments"],
                mode=EDX_ENROLLMENT_VERIFIED_MODE,
                force_enrollment=force_enrollment,
            )
            if not successful_enrollments:
                raise CommandError("Failed to create the enrollment record")
            order = PendingOrder.create_from_product(product, user, discount)
            fulfill_completed_order(
                order, payment_data=ZERO_PAYMENT_DATA, already_enrolled=True
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Enrollment created for user {} in {} (edX enrollment success: {})".format(
                    user, options["run"], edx_request_success
                )
            )
        )
