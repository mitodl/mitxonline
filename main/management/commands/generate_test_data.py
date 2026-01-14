"""
Meta-command to help set up a freshly configured MITxOnline instance.


"""

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    """
    Bootstraps a fresh MITxOnline instance.
    """

    def add_arguments(self, parser):
        """Parses command line arguments."""

        parser.add_argument(
            "platform",
            help="Your platform (none, macos, or linux; defaults to none). None skips OAuth2 record creation.",
            type=str,
            choices=["none", "macos", "linux"],
            nargs="?",
            const="none",
        )

    def create_instructor_pages_for_courseware(
        self, course_readable_id, num_instructors
    ):
        """Creates instructor pages for the given courseware object. Maybe pull into its own command later."""

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Probably should be in a transaction, have args to skip things, parameterize name/number of courses, etc."""
        standalone_course_readable_id = "course-v1:test+Test"
        call_command(
            "create_courseware",
            "course",
            standalone_course_readable_id,
            "Test Course",
            live=True,
            create_run="Test_Course",
            depts=["Test Department"],
            create_depts=True,
        )
        call_command(
            "create_courseware_page",
            standalone_course_readable_id,
            "--include_optional_values",
            "--live",
        )
        self.create_instructor_pages_for_courseware(standalone_course_readable_id, 3)
