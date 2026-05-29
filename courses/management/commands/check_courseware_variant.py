"""
Check a course's runs against the supported variant options. Check that the
course has a valid default set.
"""

from argparse import RawTextHelpFormatter

from django.core.management import BaseCommand
from django.core.management.base import CommandParser

from b2b.models import ContractPage
from courses.api import resolve_courseware_object_from_id
from courses.models import Course
from variants.models import SupportedVariant


class Command(BaseCommand):
    """Check course variants for validity."""

    help = """Check course variants for validity.

Ensures that the course has runs for each of the valid variant options that are
configured for the course, and makes sure there's a default option set up. If a
set of options is supported by the course but no runs exist for it, the output
will note that.

Ex: course course-v1:MITxT+1.234S has a default (lang=en, industry="", length="")
and supports a Portugese translation (lang=pt, industry="", length=""). It has
one run in English and no others, so the output would be:

    Language = en Industry =  Length =
            course-v1:MITxT+1.234S+1T2026

    Language = pt Industry =  Length =
            NO RUNS

If there were runs for Portugese, they would be displayed.

If there's no default set, the command will note that and then quit. You can use
the --fix-default flag to add a default option set to the course. The default is:
    (language = "en", industry = "", length = "")
Specifying the flag will add the default set and then perform the check.

By default, this only checks publicly-available runs. Check for runs belonging to
a contract by using --contract. Note that this checks against what is supported
by the course, which may include variant options that the contract does not include."""

    def create_parser(self, *args, **kwargs):
        """Change the formatter class so the above help is formatted better."""

        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter

        return parser

    def add_arguments(self, parser: CommandParser) -> None:
        """Add arguments to the command."""

        parser.add_argument(
            "course",
            type=str,
            help="The course readable ID to work with. (Use either this or --run.)",
        )
        parser.add_argument(
            "--contract",
            type=str,
            help="Check only the specified contract ID or slug.",
        )
        parser.add_argument(
            "--fix-default",
            action="store_true",
            help="Add a default variant if there's not one.",
        )

    def handle(self, *_args, **kwargs):  # noqa: C901
        """Perform the check."""

        course = kwargs.pop("course")
        contract = kwargs.pop("contract", False)
        contract_obj = False

        course_obj = resolve_courseware_object_from_id(courseware_id=course)

        if not isinstance(course_obj, Course):
            self.stderr.write(
                self.style.ERROR(f"Value {course} is not a valid course.")
            )
            return

        if contract:
            if contract.isdecimal():
                contract_obj = ContractPage.objects.filter(id=contract).first()
            else:
                contract_obj = ContractPage.objects.filter(slug=contract).first()

            if not contract_obj:
                self.stderr.write(
                    self.style.ERROR(f"Value {contract} is not a valid contract.")
                )
                return

            self.stdout.write(f"Checking for contract {contract_obj}")
        else:
            self.stdout.write("Checking publicly-available courses")

        default_variant = course_obj.default_variant_options

        if not default_variant:
            self.stderr.write(
                self.style.ERROR(
                    f"Course {course_obj.readable_id} doesn't have a default variant set."
                )
            )

            if kwargs.pop("fix_default", False):
                self.stdout.write(
                    "'fix-default' flag set, creating a default variant set for the course."
                )
                default_variant = SupportedVariant.objects.create(
                    variant_object=course_obj,
                    language="en",
                    b2b_only=False,
                    default_variant=True,
                )
            else:
                return

        other_options = course_obj.possible_variant_sets.filter(
            default_variant=False, b2b_only=bool(contract_obj)
        )

        self.stdout.write(
            f"{len(other_options)} supported variants + default for course {course_obj.readable_id}"
        )

        runs_qs = course_obj.courseruns.filter(
            b2b_contract=(contract_obj if contract_obj else None)
        )

        seen_run_ids = []

        for variant in [default_variant, *other_options.all()]:
            variant_runs = runs_qs.filter(variant.to_q_filter()).all()

            runs = []

            for variant_run in variant_runs:
                source_flag = "(Source)" if variant_run.is_source_run else ""
                runs.append(f"{variant_run.courseware_id}{source_flag}")
                seen_run_ids.append(variant_run.id)

            runs = " ".join(runs) if len(runs) > 0 else self.style.WARNING("NO RUNS")

            self.stdout.write(
                f"Language = {variant.language} Industry = {variant.variant_industry} Length = {variant.variant_length}"
            )
            self.stdout.write(f"\t{runs}")

        unseen_runs = runs_qs.exclude(pk__in=seen_run_ids).all()

        if unseen_runs.count():
            self.stdout.write(f"\nNon-matching runs ({unseen_runs.count()} total)")

            for run in unseen_runs:
                primary = (
                    "(Primary)" if run.language == "" or run.is_primary_language else ""
                )
                self.stdout.write(
                    f"\t{run.courseware_id} - {run.run_tag}: Language = {run.language}{primary} Industry = {run.variant_industry} Length = {run.variant_length}"
                )
