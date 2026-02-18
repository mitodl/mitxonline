"""
Sets up test data for e2e playwright tests as defined in mit-learn.

Running this will perform the following functions in a transaction:
- Creating a program.
- Creating financial assistance tiers, and a flexible price request form for
  the program.
- Creating course entries for the default courses w/ courseruns.
- Creating product entries and course about pages for these courses, each of which is set to 999 dollars
- CMS pages for the program and courses, instructor pages and certificate pages.


What doesn't this do?
- Set up organizations/contracts. This will be something we want to add shortly.
- Any user management. We need to figure out what this should look like in service of mutative tests.
- Sync w/ any external datasource (i.e. edx).
- Attempt to overwrite existing state/blow away any modifications. We will need to solve this somehow for things like courseruns which expire, but we can start here.
"""

import sys
from decimal import Decimal

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.db import transaction

from b2b.api import _create_discount_with_product
from b2b.models import ContractPage
from ecommerce.constants import REDEMPTION_TYPE_UNLIMITED

PLACEHOLDER_PROGRAM_ID = "program-v1:PLACEHOLDER+PROGRAM"


class Command(BaseCommand):
    """
    Bootstraps necessary course-related data for core tests.
    """

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
                PLACEHOLDER_PROGRAM_ID,
                "PLACEHOLDER - Data, Economics and Development Policy",
                live=True,
                depts=["PLACEHOLDER - Economics"],
                create_depts=True,
                create_page=True,
                create_certificate_page=True,
                create_signatory=True,
                set_courserun_dates_automatically=True,
            )

            # Step 2: create the financial aid form
            self.stdout.write(
                self.style.SUCCESS(
                    "Creating the Placeholder financial assistance form..."
                )
            )

            if not settings.OPEN_EXCHANGE_RATES_APP_ID:
                self.stderr.write(
                    self.style.WARNING(
                        "OPEN_EXCHANGE_RATES_APP_ID not set. Please set value from RC to continue"
                    )
                )
                sys.exit(1)
            call_command(
                "load_country_income_thresholds",
                "flexiblepricing/data/country_income_thresholds.csv",
            )
            call_command("configure_tiers", program=PLACEHOLDER_PROGRAM_ID)
            call_command("update_exchange_rates")
            call_command("create_finaid_form", PLACEHOLDER_PROGRAM_ID, live=True)

            # Step 3: create the courses (incld. course runs)
            self.stdout.write(self.style.SUCCESS("Creating courses and runs"))

            call_command(
                "create_courseware",
                "course",
                "course-v1:PLACEHOLDER+COURSE_IN_PROGRAM_REQUIRED",  # This course ID must have one plus, course runs must have 2.
                "PLACEHOLDER - Demonstration Course in Program (Required)",
                live=True,
                create_run="PLACEHOLDER_Demo_Course_in_Program_Required",
                create_run_as_sourcerun=True,
                program=PLACEHOLDER_PROGRAM_ID,
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
                "course-v1:PLACEHOLDER+COURSE_IN_PROGRAM_ELECTIVE",
                "PLACEHOLDER - Demonstration Course in Program (Elective)",
                live=True,
                create_run="PLACEHOLDER_Demo_Course_in_Program_Elective",
                create_run_as_sourcerun=True,
                program=PLACEHOLDER_PROGRAM_ID,
                elective=True,  # Required or elective must be specified if course is in a program
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
                create_run_as_sourcerun=True,
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
                readable_ids=f"course-v1:PLACEHOLDER+COURSE_IN_PROGRAM_REQUIRED,course-v1:PLACEHOLDER+COURSE_IN_PROGRAM_ELECTIVE,course-v1:PLACEHOLDER+COURSE,{PLACEHOLDER_PROGRAM_ID}",
            )

            # create_product only works for Courses. We need to see if products for programs are useful.
            # Having this allows us to select a certificate course and get to the checkout page.
            call_command(
                "create_product",
                "course-v1:PLACEHOLDER+COURSE_IN_PROGRAM_REQUIRED+PLACEHOLDER_Demo_Course_in_Program_Required",
                999,
            )
            call_command(
                "create_product",
                "course-v1:PLACEHOLDER+COURSE_IN_PROGRAM_ELECTIVE+PLACEHOLDER_Demo_Course_in_Program_Elective",
                999,
            )

            # Create an organization and enrollment code contract along w/ their CMS pages (which are live)
            call_command(
                "b2b_contract",
                "create",
                "test_organization",
                "test_contract",
                "code",
                description="This is a test contract",
                create=True,
                org_key="test_organization",
            )

            call_command(
                "b2b_courseware", "add", "test_contract", PLACEHOLDER_PROGRAM_ID
            )

            # Marginally scuffed, but we want to create codes with known values for use in tests
            contract = ContractPage.objects.get(name="test_contract")
            products = contract.get_products()
            course_runs_map = {run.id: run for run in contract.get_course_runs()}
            for product in products:
                corresponding_run = course_runs_map[product.object_id]
                # Run tag includes the current year, so it's not ideal, but it's stable enough for us to start with.
                code = corresponding_run.courseware_id
                self.stdout.write(f"Creating discount with code: {code}")
                _create_discount_with_product(
                    product, Decimal(0), REDEMPTION_TYPE_UNLIMITED, code_override=code
                )

            # In the future, it might make more sense to use one of the Keycloak provided users.
            # Since they're provisioned at first login, I'm not sure if I can create them here without screwing up their use for manual login
            call_command(
                "create_user",
                "testlearner",
                "testlearner@mitxonline.odl.local",
                "Test",
                "Learner",
                "Test Learner",
                "US",
                password="testpassword123",  # noqa: S106
            )
