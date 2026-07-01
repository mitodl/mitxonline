"""Report missing CMS product and certificate pages for courses and programs."""

from django.core.management.base import BaseCommand

from courses.models import Course, Program


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

    def handle(self, *args, **options):  # noqa: ARG002
        live_only = options["live"]
        show_details = options["details"]

        courses_qs = Course.objects.all()
        programs_qs = Program.objects.all()
        if live_only:
            courses_qs = courses_qs.filter(live=True)
            programs_qs = programs_qs.filter(live=True)

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
