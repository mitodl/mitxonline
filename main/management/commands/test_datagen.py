# ruff: noqa: ERA001 TD002 FIX002 TD003
"""
Meta-command to help set up a freshly configured MITxOnline instance.

Running this will perform the following functions:
- Creating a program.
- Creating financial assistance tiers, and a flexible price request form for
  the program.
- Creating course entries for the default courses.
- Creating product entries and course about pages for these courses.
- CMS pages for the program and courses.

The product for the courses will both be $999 so they are under the limit
for test CyberSource transactions.


What doesn't this do?
- Any user management.
"""

from django.core.management import BaseCommand, call_command
from django.db import transaction


class Command(BaseCommand):
    """
    Bootstraps necessary course-related data for core tests.
    """

    def add_arguments(self, parser):
        """Parses command line arguments."""

        parser.add_argument(
            "--dont-create-superuser",
            "-S",
            help="Don't create a superuser account.",
            action="store_false",
            dest="superuser",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Coordinates the other commands."""

        with transaction.atomic():
            # Step 1: create the program
            self.stdout.write(
                self.style.SUCCESS("Creating the Placeholder program and CMS pages...")
            )

            call_command(
                "create_courseware",
                "program",
                "program-v1:PLACEHOLDER+PROGRAM",
                "PLACEHOLDER - Data, Economics and Development Policy",
                live=True,
                depts=["PLACEHOLDER - Economics"],
                create_depts=True,
                create_page=True,
                create_certificate_page=True,
                create_signatory=True,
                set_courserun_dates_automatically=True,
            )

            # Step 4: create the financial aid form
            self.stdout.write(
                self.style.SUCCESS(
                    "Creating the Placeholder financial assistance form..."
                )
            )

            call_command("create_finaid_form", "program-v1:PLACEHOLDER+PROGRAM")

            # Step 5: create the courses (incld. course runs)
            self.stdout.write(self.style.SUCCESS("Creating courses and runs"))

            call_command(
                "create_courseware",
                "course",
                "course-v1:PLACEHOLDER+COURSE+IN+PROGRAM+REQUIRED",
                "PLACEHOLDER - Demonstration Course in Program (Required)",
                live=True,
                create_run="PLACEHOLDER_Demo_Course_in_Program_Required",
                program="program-v1:PLACEHOLDER+PROGRAM",
                required=True,  # Required or elective must be specified if course is in a program
                depts=["Science"],
                create_depts=True,
                create_page=True,
                create_certificate_page=True,
                create_signatory=True,
                set_courserun_dates_automatically=True,
            )
            call_command(
                "create_courseware",
                "course",
                "course-v1:PLACEHOLDER+COURSE+IN+PROGRAM+ELECTIVE",
                "PLACEHOLDER - Demonstration Course in Program (Elective)",
                live=True,
                create_run="PLACEHOLDER_Demo_Course_in_Program_Elective",
                program="program-v1:PLACEHOLDER+PROGRAM",
                required=True,  # Required or elective must be specified if course is in a program
                depts=["Science"],
                create_depts=True,
                create_page=True,
                create_certificate_page=True,
                create_signatory=True,
                set_courserun_dates_automatically=True,
            )

            call_command(
                "create_courseware",
                "course",
                "course-v1:PLACEHOLDER+COURSE",
                "PLACEHOLDER - E2E Test Course",
                live=True,
                create_run="PLACEHOLDER_E2E_Test_Course",
                depts=["Math"],
                create_depts=True,
                create_page=True,
                create_certificate_page=True,
                create_signatory=True,
                set_courserun_dates_automatically=True,
            )

            call_command(
                "create_instructor_pages",
                fake=True,
                readable_ids="course-v1:PLACEHOLDER+COURSE+IN+PROGRAM+REQUIRED,course-v1:PLACEHOLDER+COURSE+IN+PROGRAM+ELECTIVE,course-v1:PLACEHOLDER+COURSE,program-v1:PLACEHOLDER+PROGRAM",
            )

            # Step 7: create the products
            # TODO: Unclear if I need this... comment out for now.
            # self.stdout.write(
            #     self.style.SUCCESS("Creating the devstack course products...")
            # )
            #
            # call_command("create_product", "course-v1:edX+E2E-101+course", 999)
            # call_command("create_product", "course-v1:edX+DemoX+Demo_Course", 999)
            # call_command(
            #     "createinitialrevisions", "ecommerce.Product", comment="Initial revision."
            # )
