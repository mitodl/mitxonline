"""
"Imports" a course run from the configured edX instance, and optionally creates
some infrastructure pieces to go along with it.

This will grab:
* Start/end dates
* Enrollment start/end dates
* Name
* Pacing status

from edX using the course detail API, and then will use that to create a course
run in MITx Online. Optionally, you can supply a run tag (e.g. 1T2023) and a
program (program-v1:MITx+DEDP) to have it cycle through the courses that are
associated with the program and attempt to grab courses from edX. If the course
run already exists in MITx Online, it will be skipped (the normal sync will
take care of it). If the creation is successful, this will optionally run the
create_courseware_page command for the course run.
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management import BaseCommand

from courses.api import import_courserun_from_edx
from courses.models import Program
from openedx.api import get_edx_api_course_detail_client

try:
    from b2b.models import ContractPage
except ImportError:
    ContractPage = None


class Command(BaseCommand):
    """
    Creates a courseware object.
    """

    help = "Creates a course run using details from edX. Supports setting catalog/AI flags, CMS page creation options, and B2B contract assignment."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--courserun",
            type=str,
            nargs="?",
            help="The course run to create. Do not specify with --program.",
        )

        parser.add_argument(
            "--program",
            type=str,
            nargs="?",
            help="The program to iterate through. Can be the readable ID or the database ID. Requires --run-tag. Do not specify with --courserun.",
        )

        parser.add_argument(
            "--run-tag",
            type=str,
            nargs="?",
            help="The run tag (3T2022, etc.) to use. The + will be appended to this when combining it with the course's readable ID. Requires --program. Do not specify with --courserun.",
        )

        parser.add_argument(
            "--live",
            action="store_true",
            help="Make the new course run live (defaults to not).",
        )

        parser.add_argument(
            "--create-cms-page",
            action="store_true",
            help="Create a draft CMS page for the course too",
        )

        parser.add_argument(
            "--price",
            help="Create a matching product with the specified price for the generated course run(s).",
            type=str,
            nargs="?",
        )

        parser.add_argument(
            "--block_countries",
            type=str,
            help="Comma separated list of countries to block enrollments. Both Country Name and ISO code are supported",
            nargs="?",
        )

        parser.add_argument(
            "-d",
            "--dept",
            "--department",
            help="Specify department(s) assigned to the course object.  If program is specified, all courses associated with the program and imported will have the same department.",
            action="append",
            dest="depts",
        )

        parser.add_argument(
            "--create-depts",
            action="store_true",
            help="Create any departments that need to be created.",
        )

        parser.add_argument(
            "--include-in-learn-catalog",
            action="store_true",
            help="Include this course in the Learn catalog (sets include_in_learn_catalog flag on CMS page).",
        )

        parser.add_argument(
            "--ingest-content-files-for-ai",
            action="store_true",
            help="Allow AI chatbots to ingest the course's content files (sets ingest_content_files_for_ai flag on CMS page).",
        )

        parser.add_argument(
            "--publish-cms-page",
            action="store_true",
            help="Explicitly publish the CMS page when --create-cms-page is used. By default, the CMS page follows the --live flag.",
        )

        parser.add_argument(
            "--draft-cms-page",
            action="store_true",
            help="Explicitly create a draft CMS page when --create-cms-page is used. By default, the CMS page follows the --live flag.",
        )

        parser.add_argument(
            "--contract",
            type=str,
            help="Assign the resulting course run to the specified B2B contract (contract ID or slug).",
        )

        parser.add_argument(
            "--source-course",
            action="store_true",
            help="Designate the course run(s) to import as source course runs.",
        )

    def _resolve_contract(self, contract_identifier):
        """
        Resolve a contract by ID or slug.

        Args:
            contract_identifier (str): Contract ID (numeric) or slug

        Returns:
            ContractPage or None: The resolved contract or None if not found/not available
        """
        if not ContractPage or not contract_identifier:
            return None

        if contract_identifier.isdigit():
            try:
                return ContractPage.objects.get(id=int(contract_identifier))
            except ContractPage.DoesNotExist:
                pass

        try:
            return ContractPage.objects.get(slug=contract_identifier)
        except ContractPage.DoesNotExist:
            pass

        return None

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: C901, PLR0915, ARG002
        if kwargs.get("publish_cms_page") and kwargs.get("draft_cms_page"):
            self.stderr.write(
                self.style.ERROR(
                    "Cannot specify both --publish-cms-page and --draft-cms-page."
                )
            )
            return False

        edx_course_detail = get_edx_api_course_detail_client()
        edx_courses = []

        contract = None
        if kwargs.get("contract"):
            contract = self._resolve_contract(kwargs.get("contract"))
            if not contract:
                self.stdout.write(
                    self.style.ERROR(
                        f"Contract '{kwargs.get('contract')}' not found or B2B module not available."
                    )
                )
                return False

        price = None
        if kwargs.get("price"):
            try:
                # Validate that price is a valid decimal
                Decimal(kwargs.get("price"))
                price = kwargs.get("price")
            except (ValueError, TypeError, InvalidOperation):
                self.stdout.write(
                    self.style.WARNING(
                        f"Invalid price format: {kwargs.get('price')}. Must be a valid decimal number. Skipping product creation."
                    )
                )
                price = None

        publish_cms_page = False

        if kwargs.get("live") or kwargs.get("publish_cms_page"):
            publish_cms_page = True

        if kwargs.get("live") and kwargs.get("draft_cms_page"):
            publish_cms_page = False

        if kwargs.get("courserun") is not None:
            try:
                course = edx_course_detail.get_detail(
                    course_id=kwargs.get("courserun"),
                    username=settings.OPENEDX_SERVICE_WORKER_USERNAME,
                )

                if course is not None:
                    edx_courses.append(course)
            except Exception as e:  # noqa: BLE001
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not retrieve data for {kwargs.get('courserun')}: {e}"
                    )
                )
                return False
        elif kwargs.get("program") is not None and kwargs.get("run_tag") is not None:
            try:
                if kwargs.get("program").isnumeric():
                    program = Program.objects.filter(pk=kwargs.get("program")).get()
                else:
                    program = Program.objects.filter(
                        readable_id=kwargs.get("program")
                    ).get()
            except:  # noqa: E722
                self.stdout.write(
                    self.style.ERROR(f"Program {kwargs.get('program')} not found.")
                )
                return False
            for course, title in program.courses:  # noqa: B007
                if course.courseruns.filter(run_tag=kwargs.get("run_tag")).count() == 0:
                    try:
                        edx_course = edx_course_detail.get_detail(
                            course_id=f"{course.readable_id}+{kwargs.get('run_tag')}",
                            username=settings.OPENEDX_SERVICE_WORKER_USERNAME,
                        )

                        if edx_course is not None:
                            edx_courses.append(edx_course)
                    except Exception as e:  # noqa: BLE001
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not retrieve data for {course.readable_id}+{kwargs.get('run_tag')}, skipping it: {e}"
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"{course.readable_id}+{kwargs.get('run_tag')} appears to exist in MITx Online, skipping it"
                        )
                    )

        success_count = 0

        for edx_course in edx_courses:
            run_data = import_courserun_from_edx(
                course_key=edx_course.course_id,
                live=kwargs.get("live", False),
                price=price,
                block_countries=kwargs.get("block_countries"),
                departments=kwargs.get("depts"),
                create_depts=kwargs.get("create_depts", False),
                create_cms_page=kwargs.get("create_cms_page", False),
                publish_cms_page=publish_cms_page,
                include_in_learn_catalog=kwargs.get("include_in_learn_catalog", False),
                ingest_content_files_for_ai=kwargs.get(
                    "ingest_content_files_for_ai", False
                ),
                is_source_run=kwargs.get("source_course", False),
            )

            if run_data:
                (run, page, product) = run_data

                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created new run {run.courseware_id} in course {run.course.readable_id}"
                    )
                )

                if page:
                    self.stdout.write(self.style.SUCCESS(f"\t --> Created page {page}"))

                if product:
                    self.stdout.write(
                        self.style.SUCCESS(f"\t --> Created product {product}")
                    )

        self.stdout.write(self.style.SUCCESS(f"{success_count} course runs created"))
        return None
