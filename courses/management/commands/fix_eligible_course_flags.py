"""
Fix the flags on eligible course runs so that they're right for Learn and Learn AI.

The include_in_learn_catalog and ingest_content_files_for_ai flags control
whether or not the given course should appear in the Learn catalog, and whether
or not the AI chatbots should ingest content files for the course's runs. These
default to False, but we can _usually_ determine whether or not a course should
have them set to True based on whether or not the course is enrollable, has a
published marketing page, and has B2B course runs.

These can be overridden, and in some cases we may want to (say) manually flag a
course for ingestion or not, so we don't do this automatically. This command will
overwrite the flags so running it without filters should be done with care.

"""

from django.core.management import BaseCommand
from django.db.models import Count, Q

from courses.models import Course, ProgramRequirement, ProgramRequirementNodeType
from courses.utils import get_enrollable_courses


class Command(BaseCommand):
    """Finds and updates the ingestion and Learn catalog flags on courses."""

    help = "Finds and updates the ingestion and Learn catalog flags on courses."

    def add_arguments(self, parser):
        """Add arguments to the command"""

        parser.add_argument(
            "--dry-run",
            type=bool,
            help="Determine what needs to change, but don't make any changes.",
        )
        parser.add_argument(
            "--course",
            type=str,
            help="Check the specified course by readable ID",
            nargs="*",
            action="extend",
        )
        parser.add_argument(
            "--program",
            type=str,
            help="Consider courses within the specified program",
            nargs="*",
            action="extend",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Get the courses and figure out what changes to make"""

        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    "Dry run mode on - no database changes will be made."
                )
            )

        courses_base_qs = (
            get_enrollable_courses(Course.objects.all())
            .annotate(
                Count("courseruns", filter=Q(courseruns__b2b_contract__isnull=True)),
                "regular_courserun_count",
            )
            .annotate(
                Count("courseruns", filter=Q(courseruns__b2b_contract__isnull=False)),
                "b2b_courserun_count",
            )
        )

        if "course" not in options and "program" not in options:
            self.stdout.write(
                self.style.WARNING(
                    "Warning - no filter applied. Changes will apply to all course records."
                )
            )

        if "course" in options:
            courses_base_qs = courses_base_qs.filter(readable_id__in=options["course"])
        if "program" in options:
            # get the programs, then get the courses in their requirements, something like that
            program_req_readable_ids = (
                ProgramRequirement.objects.filter(
                    program__readable_id__in=options["program"],
                    node_type=ProgramRequirementNodeType.COURSE,
                )
                .select_related("course")
                .values_list("course__readable_id", flat=True)
                .all()
            )

            courses_base_qs = courses_base_qs.filter(
                readable_id_in=program_req_readable_ids
            )

        ingest_qs = courses_base_qs
        ingest_qs = ingest_qs.filter(b2b_courserun_count_gt=0).all()

        updated_count = (
            ingest_qs.count()
            if dry_run
            else ingest_qs.update(ingest_content_files_for_ai=True)
        )

        self.stdout.write(
            self.style.SUCCESS(f"Set ingestion flag on {updated_count} courses")
        )

        include_qs = courses_base_qs
        include_qs = include_qs.filter(
            Q(regular_courserun_count=0) | Q(page__live__istrue=True)
        ).all()

        updated_count = (
            include_qs.count()
            if dry_run
            else include_qs.update(include_in_learn_catalog=True)
        )

        self.stdout.write(
            self.style.SUCCESS(f"Set Learn catalog flag on {updated_count} courses")
        )
