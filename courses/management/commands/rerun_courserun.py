"""Re-run a course."""

import logging
from argparse import RawTextHelpFormatter
from decimal import Decimal

import reversion
from django.core.management import BaseCommand, CommandError
from django.db import transaction
from opaque_keys.edx.keys import CourseKey

from courses.api import resolve_courseware_object_from_id
from courses.models import CourseRun
from ecommerce.models import Product
from openedx.api import process_course_run_clone

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Re-run a course."""

    help = """Re-run an existing course or course run.

Re-running a course will find the source course run for the specified course and then request a re-run of it in edX, with the specified run tag and any optional settings. A record in MITx Online will be created for the new run. The course must have a source run, however; if there's not one, you will get an error message.

Re-running a specific course run will request a re-run of the specified run from edX, regardless of whether it's a source run, with the specified run tag and any optional settings.

In either case, the command will try to create a new run. If it exists in edX already, then this will fail. If you want to pull in a run that exists, you probably want the import_courserun command.
    """

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.formatter_class = RawTextHelpFormatter

        parser.add_argument(
            "course",
            help="The course or course run (readable ID or numeric ID) to re-run. If specifying a course, the course must have a source run set up.",
            type=str,
        )

        parser.add_argument(
            "--run-tag", type=str, help="The run tag to use for the new run."
        )

        parser.add_argument(
            "--organization",
            "--org",
            type=str,
            help='The organization key to use (the first bit after "course-v1:"). Optional; you probably don\'t need to change this.',
        )

        parser.add_argument(
            "--change-course-org",
            action="store_true",
            help="If set, change the upstream course's org key to what's set for --organization. Will not change existing runs; requires --organization.",
        )

        parser.add_argument(
            "--keep-product",
            action="store_true",
            help="If set, create a new product for the new run that mirrors the prior run's product. Overrides --price.",
        )

        parser.add_argument(
            "--price",
            type=Decimal,
            help="If set, create a new product for the new run with the specified price.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002, C901
        """Create the re-run according to the options passed."""

        course_opt = kwargs.pop("course", None)

        run_to_clone = resolve_courseware_object_from_id(course_opt)

        if not run_to_clone:
            msg = f"Course/run {course_opt} not found."
            raise CommandError(msg)

        if not run_to_clone.is_run:
            source = run_to_clone.courseruns.filter(is_source_run=True)

            if source.count() > 1:
                msg = f"Course {course_opt} has more than one source run"
                raise CommandError(msg)

            if source.count() < 1:
                msg = f"Course {course_opt} has no source run"
                raise CommandError(msg)

            run_to_clone = source.first()

        # next steps for this:
        # - look through create_contract_run and either adapt or something to create the run
        # - make new key for the new run
        # - grab products and recreate where necessary
        # - update upstream course where necessary

        self.stdout.write(f"Rerunning {run_to_clone.courseware_id}...")

        new_key = CourseKey.from_string(run_to_clone.courseware_id)

        run_tag = kwargs.pop("run_tag")

        if not run_tag:
            msg = "Run tag is required."
            raise CommandError(msg)

        org = kwargs.pop("organization")

        if not org:
            org = new_key.org

        new_key = new_key.replace(run=run_tag)
        new_key = new_key.replace(org=org)
        self.stdout.write(f"The new course's key will be: {new_key}")

        with transaction.atomic():
            # This gets wrapped in a transaction so we can bail out if the edX
            # process fails. There is the potential that the edX process will
            # half succeed, which means we'll have an edX course that we're stuck
            # with and no course run locally. Need to fix this.
            new_course_run = CourseRun.objects.create(
                course=run_to_clone.course,
                title=run_to_clone.title,
                courseware_id=str(new_key),
                run_tag=str(new_key),
                start_date=run_to_clone.start_date,
                end_date=run_to_clone.end_date,
                enrollment_start=run_to_clone.start_date,
                enrollment_end=run_to_clone.end_date,
                certificate_available_date=run_to_clone.start_date,
                is_self_paced=run_to_clone.is_self_paced,
                live=run_to_clone.live,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Made new MITx Online course run {new_course_run.id}: {new_course_run}"
                )
            )

            if not process_course_run_clone(new_course_run.id, base_id=run_to_clone.courseware_id, set_ingest_flag=False):
                msg = f"Unable to re-run {run_to_clone} to {new_course_run}."
                raise CommandError(msg)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Made new edX course run {new_course_run}"
                )
            )

        if kwargs.pop("change_course_org", False):
            self.stdout.write(f"Updating the org key on course {run_to_clone.course} to {org}...")

            course_key = CourseKey.from_string(f"{run_to_clone.course.readable_id}+RunTag")
            course_key = course_key.replace(org=org)

            run_to_clone.course.readable_id = f"{course_key.CANONICAL_NAMESPACE}:{course_key.org}+{course_key.course}"
            run_to_clone.course.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated course key to {run_to_clone.course.readable_id}"
                )
            )

        keeping_product = kwargs.pop("keep_product", False)

        if keeping_product:
            self.stdout.write(f"Copying products for {run_to_clone} to {new_course_run}")

            with reversion.create_revision():
                for original_product in run_to_clone.products.all():
                    new_product = Product.objects.create(
                        purchasable_object=new_course_run,
                        price=original_product.price,
                        is_active=original_product.is_active,
                        description=new_course_run.courseware_id,
                    )
                    self.stdout.write(f"Created product {new_product}")

        price = kwargs.pop("price", None)

        if price and not keeping_product:
            self.stdout.write(f"Creating product for {new_course_run}")

            with reversion.create_revision():
                new_product = Product.objects.create(
                    purchasable_object=new_course_run,
                    price=price,
                    is_active=True,
                    description=new_course_run.courseware_id,
                )
                self.stdout.write(f"Created product {new_product}")
