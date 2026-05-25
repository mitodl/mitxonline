"""
Check course variants for validity.
"""

from django.core.management import BaseCommand
from django.core.management.base import CommandParser

from b2b.models import ContractPage
from courses.api import resolve_courseware_object_from_id
from courses.models import Course
from variants.models import SupportedVariant


class Command(BaseCommand):
    """Check course variants for validity."""

    help = "Check course variants for validity. By default, only checks publicly-available runs."

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

    def handle(self, *_args, **kwargs):
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

        for variant in [default_variant, *other_options.all()]:
            variant_runs = runs_qs.filter(variant.to_q_filter()).all()

            runs = []

            for variant_run in variant_runs:
                source_flag = "(Source)" if variant_run.is_source_run else ""
                runs.append(f"{variant_run.courseware_id}{source_flag}")

            runs = " ".join(runs) if len(runs) > 0 else self.style.WARNING("NO RUNS")

            self.stdout.write(
                f"Language = {variant.language} Industry = {variant.variant_industry} Length = {variant.variant_length}"
            )
            self.stdout.write(f"\t{runs}")
