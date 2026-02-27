"""Re-run a course."""

import logging
from argparse import RawTextHelpFormatter
from decimal import Decimal

from django.core.management import BaseCommand, CommandError
from opaque_keys import InvalidKeyError

from b2b.api import create_contract_run, import_and_create_contract_run
from b2b.models import ContractPage, ContractProgramItem
from courses.api import resolve_courseware_object_from_id
from courses.constants import UAI_COURSEWARE_ID_PREFIX
from courses.models import CourseRun

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
            "--contract",
            type=str,
            help="The B2B contract (slug or numeric ID) to which the new run should belong. Optional; overrides --run-tag.",
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
            help="If set, create a new product for the new run that mirrors the prior run's product.",
        )

        parser.add_argument(
            "--price",
            type=Decimal,
            help="If set, create a new product for the new run with the specified price.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Create the re-run according to the options passed."""

        course_opt = kwargs.pop("course", None)

        courseware = resolve_courseware_object_from_id(course_opt)

        if not courseware:
            msg = f"Course/run {course_opt} not found."
            raise CommandError(msg)

        if not courseware.is_run:
            source = courseware.courseruns.filter(is_source_run=True)

            if source.count() > 1:
                msg = f"Course {course_opt} has more than one source run"
                raise CommandError(msg)

            if source.count() < 1:
                msg = f"Course {course_opt} has no source run"
                raise CommandError(msg)

            courseware = source.first()

        # next steps for this:
        # - look through create_contract_run and either adapt or something to create the run
        # - make new key for the new run
        # - grab products and recreate where necessary
        # - update upstream course where necessary
        
