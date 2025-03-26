
from datetime import timedelta, datetime
import pytz
from django.contrib.contenttypes.models import ContentType
from mitol.common.utils import now_in_utc

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cms.factories import CoursePageFactory
from cms.models import CoursePage, HomePage, CourseIndexPage
from courses.management.utils import load_json_from_file
from courses.models import CourseRun, Course, Department
from ecommerce.models import Product
from users.api import fetch_user

User = get_user_model()

COURSE_DATA_PATH = 'courses/management/courses.json'
FAKE_COURSE_DESC_PREFIX = '[FAKE] '


def generate_run_defaults(run):
    """Generates default values for a CourseRun based on the provided run data"""
    now = now_in_utc()
    run_defaults = {
        "run_tag": f"{run['run_tag']}{now.year}",
        "live": True,
        "title": run['title'],
        "upgrade_deadline": f"{now.year}{run['upgrade_deadline']}"
    }

    if run["is_enrollable"]:
        run_defaults['enrollment_start'] = f"{now.year}{run['enrollment_start']}"
        run_defaults['enrollment_end'] = f"{now.year}{run['enrollment_end']}"
        run_defaults["start_date"] = f"{now.year}{run['start_date']}"
        run_defaults['end_date'] = f"{now.year}{run['end_date']}"
    if run['is_archived']:
        # If the run is archived, set the start and end dates to be in the past
        previous_year = (now-timedelta(days=365)).year
        run_defaults['start_date'] = f"{previous_year}{run['start_date']}"
        run_defaults['end_date'] = f"{previous_year}{run['end_date']}"
        run_defaults['enrollment_start'] = f"{previous_year}{run['enrollment_start']}"
        run_defaults['enrollment_end'] = f"{now.year}{run['enrollment_end']}"
        run_defaults["run_tag"] = f"{run['run_tag']}{previous_year}"

    return run_defaults


def create_courses_from_data_list(course_data_list):
    """Deserializes a list of Course data"""
    courses = []
    department, _ = Department.objects.get_or_create(name="Test Scenarios Department", slug="test-scenarios-department")
    for course_data in course_data_list:
        course_defaults = {
            "title": course_data['title'],
            "readable_id": course_data['readable_id'],
            "live": True,
        }
        # Set the description to make this course easily identifiable as a 'fake'
        # Create the course and its course runs
        course, created = Course.objects.update_or_create(title=course_data['title'], defaults=course_defaults)

        if not CoursePage.objects.filter(course=course).exists():
            course_cms_page = CoursePage(
                course=course,
                title=course_data['title'],
                description=FAKE_COURSE_DESC_PREFIX + course_data['description'],
                min_weekly_hours=course_data['min_weekly_hours'],
                max_weekly_hours=course_data['max_weekly_hours'],
                length=course_data['length'],
            )
            course_cms_page.custom_tabs = ["content", "instructors", "faq"]
            course_index = CourseIndexPage.objects.first()
            course_index.add_child(instance=course_cms_page)

            course_cms_page.save_revision().publish()

        for run in course_data['course_runs']:
            run_defaults = generate_run_defaults(run)

            course_run, created = CourseRun.objects.update_or_create(
                course=course,
                courseware_id=run['courseware_id'],
                defaults=run_defaults
            )
            if created:
                course.courseruns.add(course_run)

            ### Create a product for the course run
            course_run_content_type = ContentType.objects.get(
                app_label="courses", model="courserun"
            )
            if run["is_upgradable"]:
                product, created = Product.objects.update_or_create(
                        object_id=course_run.id,
                        content_type=course_run_content_type,
                        is_active=True,
                        defaults={"description": course_run.courseware_id, "price": run['price']},
                )

        if created:
            course.departments.add(department)

    return courses


class Command(BaseCommand):
    """
    Seed the database with a set course, course run data, for testing purposes.

    The course states should be valid for the current calendar year. When the new year comes need to run
    ./manage.py populate_course_data --update
    to update the course run dates to the current year.
    """
    help = "Seed the database with a set course, course run data, for testing purposes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            dest="update",
            help="If provided, update the existing course data instead of creating new ones.",
        )

    def handle(self, *args, **options):  # pylint: disable=too-many-locals  # noqa: ARG002
        course_data_list = load_json_from_file(COURSE_DATA_PATH)

        create_courses_from_data_list(course_data_list)

        self.stdout.write(
            self.style.SUCCESS("Created courses!")
        )

