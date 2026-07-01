"""Report missing CMS product and certificate pages for courses and programs."""

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from courses.api import get_eligible_program_certificate_candidates
from courses.models import Course, CourseRunEnrollment, CourseRunGrade, Program
from openedx.constants import EDX_ENROLLMENTS_PAID_MODES


class Command(BaseCommand):
    """Print a report of missing Course/Program pages and certificate child pages."""

    help = (
        "Report courses/programs that are missing CMS product pages or "
        "certificate child pages"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--live",
            action="store_true",
            help="Only include live courses/programs in the report.",
        )
        parser.add_argument(
            "--details",
            action="store_true",
            help="Print detailed rows for each missing item.",
        )
        parser.add_argument(
            "--eligible-users-only",
            action="store_true",
            help=(
                "Only include courses/programs where at least one user is eligible "
                "for certificates."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        live_only = options["live"]
        show_details = options["details"]
        eligible_users_only = options["eligible_users_only"]

        courses_qs = Course.objects.all()
        programs_qs = Program.objects.all()
        if live_only:
            courses_qs = courses_qs.filter(live=True)
            programs_qs = programs_qs.filter(live=True)

        if eligible_users_only:
            courses_qs = courses_qs.filter(id__in=self._eligible_course_ids())
            programs_qs = programs_qs.filter(id__in=self._eligible_program_ids())

        missing_course_pages = []
        missing_course_certificate_pages = []
        for course in courses_qs:
            try:
                course_page = course.page
            except Course.page.RelatedObjectDoesNotExist:
                missing_course_pages.append(course)
                continue

            if not course_page.certificate_page:
                missing_course_certificate_pages.append(course)

        missing_program_pages = []
        missing_program_certificate_pages = []
        for program in programs_qs:
            try:
                program_page = program.page
            except Program.page.RelatedObjectDoesNotExist:
                missing_program_pages.append(program)
                continue

            if not program_page.certificate_page:
                missing_program_certificate_pages.append(program)

        stats = {
            "missing_course_pages": len(missing_course_pages),
            "missing_course_certificate_pages": len(missing_course_certificate_pages),
            "missing_program_pages": len(missing_program_pages),
            "missing_program_certificate_pages": len(missing_program_certificate_pages),
        }

        self.stdout.write(
            self.style.WARNING(
                f"Courses missing CMS page: {stats['missing_course_pages']}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Courses missing CMS certificate page: "
                f"{stats['missing_course_certificate_pages']}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"Programs missing CMS page: {stats['missing_program_pages']}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Programs missing CMS certificate page: "
                f"{stats['missing_program_certificate_pages']}"
            )
        )

        if show_details:
            self._print_items("Course missing page", missing_course_pages)
            self._print_items(
                "Course missing certificate page", missing_course_certificate_pages
            )
            self._print_items("Program missing page", missing_program_pages)
            self._print_items(
                "Program missing certificate page", missing_program_certificate_pages
            )

        return stats

    def _print_items(self, label, items):
        if not items:
            return

        self.stdout.write(self.style.WARNING(f"{label} details:"))
        for item in items:
            self.stdout.write(
                f"- id={item.id} readable_id={item.readable_id} title={item.title}"
            )

    def _eligible_course_ids(self):
        paid_enrollment = CourseRunEnrollment.objects.filter(
            user_id=OuterRef("user_id"),
            run_id=OuterRef("course_run_id"),
            enrollment_mode__in=EDX_ENROLLMENTS_PAID_MODES,
        )

        return (
            CourseRunGrade.objects.filter(passed=True)
            .annotate(has_paid_enrollment=Exists(paid_enrollment))
            .filter(has_paid_enrollment=True)
            .values_list("course_run__course_id", flat=True)
        )

    def _eligible_program_ids(self):
        return get_eligible_program_certificate_candidates().values_list(
            "program_id", flat=True
        )
