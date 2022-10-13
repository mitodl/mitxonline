"""Management command to change enrollment status"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.api import create_run_enrollments
from courses.models import CourseRun
from ecommerce.models import DiscountRedemption, Product, Discount, DiscountProduct
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

        discount = Discount.objects.filter(discount_code=options["code"]).first()
        if not discount:
            raise CommandError(
                "That enrollment code {} does not exist".format(options["code"])
            )
        if not discount.check_validity(user):
            raise CommandError(
                "That enrollment code {} is not valid for user {}".format(
                    options["code"], options["user"]
                )
            )

        with transaction.atomic():
            successful_enrollments, edx_request_success = create_run_enrollments(
                user,
                [run],
                keep_failed_enrollments=options["keep_failed_enrollments"],
                mode=EDX_ENROLLMENT_VERIFIED_MODE,
            )
            if not successful_enrollments:
                raise CommandError("Failed to create the enrollment record")

        self.stdout.write(
            self.style.SUCCESS(
                "Enrollment created for user {} in {} (edX enrollment success: {})".format(
                    user, options["run"], edx_request_success
                )
            )
        )
