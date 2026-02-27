"""Re-run a course."""

import logging
from argparse import RawTextHelpFormatter
from decimal import Decimal

from django.core.management import BaseCommand

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
            "--course",
            help="The course (readable ID or numeric ID) to re-run. The course must have a source run. Either this or --course-run must be specified.",
            type=str,
        )

        parser.add_argument(
            "--course-run",
            "--run",
            type=str,
            help="The course run (readable ID or numeric ID) to re-run. Either this or --course must be specified.",
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
