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

from decimal import Decimal
from urllib import parse

import reversion
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django_countries import countries

from cms.api import create_default_courseware_page
from courses.models import BlockedCountry, Course, CourseRun, Program
from ecommerce.models import Product
from openedx.api import get_edx_api_course_detail_client


class Command(BaseCommand):
    """
    Creates a courseware object.
    """

    help = "Creates a course run using details from edX."

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

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        edx_course_detail = get_edx_api_course_detail_client()
        edx_courses = []

        if kwargs["price"] and kwargs["price"].isnumeric():
            content_type = ContentType.objects.filter(
                app_label="courses", model="courserun"
            ).get()

        program = None

        if kwargs["program"] is not None:
            try:
                if kwargs["program"].isnumeric():
                    program = Program.objects.filter(pk=kwargs["program"]).get()
                else:
                    program = Program.objects.filter(
                        readable_id=kwargs["program"]
                    ).get()
            except:
                self.stdout.write(
                    self.style.ERROR(f"Program {kwargs['program']} not found.")
                )
                return False

        if kwargs["courserun"] is not None:
            try:
                course = edx_course_detail.get_detail(
                    course_id=kwargs["courserun"],
                    username=settings.OPENEDX_SERVICE_WORKER_USERNAME,
                )

                if course is not None:
                    edx_courses.append(course)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not retrieve data for {kwargs['courserun']}: {e}"
                    )
                )
                return False
        elif kwargs["program"] is not None and kwargs["run_tag"] is not None:
            for course, title in program.courses:
                if course.courseruns.filter(run_tag=kwargs["run_tag"]).count() == 0:
                    try:
                        edx_course = edx_course_detail.get_detail(
                            course_id=f"{course.readable_id}+{kwargs['run_tag']}",
                            username=settings.OPENEDX_SERVICE_WORKER_USERNAME,
                        )

                        if edx_course is not None:
                            edx_courses.append(edx_course)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not retrieve data for {course.readable_id}+{kwargs['run_tag']}, skipping it: {e}"
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"{course.readable_id}+{kwargs['run_tag']} appears to exist in MITx Online, skipping it"
                        )
                    )

        success_count = 0

        for edx_course in edx_courses:
            courserun_tag = edx_course.course_id.split("+")[-1]
            course_readable_id = edx_course.course_id.removesuffix(f"+{courserun_tag}")

            try:
                (course, created) = Course.objects.get_or_create(
                    readable_id=course_readable_id,
                    defaults={
                        "title": edx_course.name,
                        "readable_id": course_readable_id,
                        "live": kwargs["live"],
                    },
                )

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
                    live=kwargs["live"],
                    is_self_paced=edx_course.is_self_paced(),
                    courseware_url_path=parse.urljoin(
                        settings.OPENEDX_API_BASE_URL,
                        f"/courses/{edx_course.course_id}/course",
                    ),
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created course run for {edx_course.course_id}: id {new_run.id}"
                    )
                )
                success_count += 1

                if kwargs["create_cms_page"]:
                    try:
                        create_default_courseware_page(
                            new_run.course, live=kwargs["live"]
                        )
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created CMS page for {new_run.course.readable_id}"
                            )
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Could not create CMS page {new_run.course.readable_id}, skipping it: {e}"
                            )
                        )

                if kwargs["price"] and kwargs["price"].isnumeric():
                    with reversion.create_revision():
                        (course_product, created) = Product.objects.update_or_create(
                            content_type=content_type,
                            object_id=new_run.id,
                            price=Decimal(kwargs["price"]),
                            description=new_run.courseware_id,
                            is_active=True,
                        )

                        course_product.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created product {course_product} for {new_run.courseware_id}"
                            )
                        )

                if kwargs["block_countries"]:
                    for code_or_name in kwargs["block_countries"].split(","):
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
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not retrieve course for {edx_course.course_id}, skipping it: {e}"
                    )
                )

        self.stdout.write(self.style.SUCCESS(f"{success_count} course runs created"))
