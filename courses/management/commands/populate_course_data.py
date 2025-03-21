
from datetime import timedelta

from mitol.common.utils import now_in_utc

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.management.utils import load_json_from_file
from courses.models import CourseRun, Course
from users.api import fetch_user

User = get_user_model()

COURSE_DATA_PATH = 'courses/management/courses.json'
FAKE_COURSE_DESC_PREFIX = '[FAKE] '


def create_course(data):
    """
    Creates a new instance of a model class and fills in field values using some supplied data
    """
    course, _ = Course.objects.get_or_create(title=data['title'], defaults=data)
    course.description = FAKE_COURSE_DESC_PREFIX + data['description']
    course.save()
    for run in data['course_runs']:
        run_defaults = generate_run_defaults(run)
        course_run = CourseRun.objects.get_or_create(courseware_id=run['courseware_id'], defaults=run_defaults)
        course.course_runs.add(course_run)
        course_run.save()
    return

def generate_run_defaults(run):
    """Generates default values for a CourseRun based on the provided run data"""
    now = now_in_utc()
    now.year
    run_tag = run["run_tag"] + str(now.year)
    future_60_days = now + timedelta(days=60)
    if run['is_archived']:
        run['end_date'] = run.get('enrollment_end')
    run_defaults = {
        'start_date': run['start_date'],
        'end_date': run['end_date'],
        'enrollment_start': run.get('enrollment_start'),
        'enrollment_end': run.get('enrollment_end'),
        'live': True,
    }

    return run_defaults

def deserialize_course_data_list(course_data_list):
    """Deserializes a list of Course data"""
    courses = []
    for course_data in course_data_list:
        # Set the description to make this course easily identifiable as a 'fake'
        course_data['description'] = FAKE_COURSE_DESC_PREFIX + course_data['description']
        course_data['live'] = True
        program = deserialize_course_run_data(course_data)
        courses.append(program)
    return courses


class Command(BaseCommand):
    """
    Seed the database with a set course, course run data, for testing purposes.
    """
    help = "Seed the database with a set course, course run data, for testing purposes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            dest="update",
            help="If provided, update the existing course data instead of creating new ones.",
        )

    def handle(self, *args, **options):  # pylint: disable=too-many-locals
        course_data_list = load_json_from_file(COURSE_DATA_PATH)

        fake_courses = Course.objects.filter(description__startswith=FAKE_COURSE_DESC_PREFIX).all()
        if fake_courses.count() > 0:
            self.stdout.write(
                "Seed data appears to already exist. To update the course run dates to current use --update flag.")
        else:
            fake_courses = deserialize_course_data_list(course_data_list)
            for course in fake_courses:
                course.save()
                self.stdout.write(f"Created course: {course.title}")

