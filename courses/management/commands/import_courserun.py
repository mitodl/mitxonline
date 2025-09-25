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
from urllib import parse

import reversion
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django_countries import countries

from cms.api import create_default_courseware_page
from courses.models import BlockedCountry, Course, CourseRun, Department, Program
from ecommerce.models import Product
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

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: C901, PLR0915
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
            courserun_tag = edx_course.course_id.split("+")[-1]
            course_readable_id = edx_course.course_id.removesuffix(f"+{courserun_tag}")
            course = Course.objects.filter(readable_id=course_readable_id)
            if kwargs.get("depts") and len(kwargs.get("depts")) > 0:
                add_depts = Department.objects.filter(
                    name__in=kwargs.get("depts")
                ).all()

            if "add_depts" not in locals() or not add_depts:
                self.stdout.write(
                    self.style.ERROR(
                        "Departments must exist and be specified with the --dept argument prior to running this command to create courses."
                    )
                )
                return False

            (course, created) = Course.objects.get_or_create(
                readable_id=course_readable_id,
                defaults={
                    "title": edx_course.name,
                    "readable_id": course_readable_id,
                    "live": kwargs.get("live", False),
                },
            )
            course.departments.set(add_depts)
            course.save()

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created course for {course_readable_id}: {course}"
                    )
                )

            new_run = CourseRun.objects.create(
                course=course,
                run_tag=courserun_tag,
                courseware_id=edx_course.course_id,
                start_date=edx_course.start,
                end_date=edx_course.end,
                enrollment_start=edx_course.enrollment_start,
                enrollment_end=edx_course.enrollment_end,
                title=edx_course.name,
                live=kwargs.get("live", False),
                is_self_paced=edx_course.is_self_paced(),
                courseware_url_path=parse.urljoin(
                    settings.OPENEDX_API_BASE_URL,
                    f"/courses/{edx_course.course_id}/course",
                ),
                b2b_contract=contract,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created course run for {edx_course.course_id}: id {new_run.id}"
                )
            )

            if contract:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned course run to contract: {contract.name} (ID: {contract.id})"
                    )
                )

            success_count += 1

            if kwargs.get("create_cms_page"):
                try:
                    # Determine whether to publish the CMS page
                    cms_page_live = kwargs.get("live", False)

                    if kwargs.get("publish_cms_page"):
                        cms_page_live = True
                    elif kwargs.get("draft_cms_page"):
                        cms_page_live = False

                    course_page = create_default_courseware_page(
                        new_run.course, live=cms_page_live
                    )

                    if kwargs.get("include_in_learn_catalog") or kwargs.get(
                        "ingest_content_files_for_ai"
                    ):
                        if kwargs.get("include_in_learn_catalog"):
                            course_page.include_in_learn_catalog = True
                        if kwargs.get("ingest_content_files_for_ai"):
                            course_page.ingest_content_files_for_ai = True
                        course_page.save()

                    status_msg = "live" if cms_page_live else "draft"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created {status_msg} CMS page for {new_run.course.readable_id}"
                        )
                    )
                except Exception as e:  # noqa: BLE001
                    self.stdout.write(
                        self.style.ERROR(
                            f"Could not create CMS page {new_run.course.readable_id}, skipping it: {e}"
                        )
                    )

            if price:
                content_type = ContentType.objects.get_for_model(CourseRun)
                with reversion.create_revision():
                    (course_product, created) = Product.objects.update_or_create(
                        content_type=content_type,
                        object_id=new_run.id,
                        defaults={
                            "price": Decimal(price),
                            "description": new_run.courseware_id,
                            "is_active": True,
                        },
                    )

                    course_product.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created product {course_product} for {new_run.courseware_id}"
                        )
                    )

            if kwargs.get("block_countries"):
                for code_or_name in kwargs.get("block_countries").split(","):
                    country_code = countries.by_name(code_or_name)
                    if not country_code:
                        country_name = countries.countries.get(code_or_name, None)
                        country_code = code_or_name if country_name else None
                    else:
                        country_name = code_or_name

                    if country_code:
                        BlockedCountry.objects.get_or_create(
                            course=course, country=country_code
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Blocked Enrollments for {country_name} ({country_code})."
                            )
                        )
                        continue

                    self.stdout.write(
                        self.style.ERROR(
                            f"Could not block country {code_or_name}. "
                            f"Please verify that it is a valid country name or code."
                        )
                    )

        self.stdout.write(self.style.SUCCESS(f"{success_count} course runs created"))
        return None
