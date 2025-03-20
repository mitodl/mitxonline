

from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.management.utils import load_json_from_file
from courses.models import CourseRun, Course
from users.api import fetch_user

User = get_user_model()

COURSE_DATA_PATH = 'courses/management/courses.json'
FAKE_COURSE_DESC_PREFIX = '[FAKE] '

def deserialize_course_run_data(course, course_run_data):
    """Deserializes a CourseRun object"""
    course_run = deserialize_model_data(
        CourseRun, course_run_data, course=course
    )
    return course_run
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


    def handle(self, *args, **options):  # pylint: disable=too-many-locals
        course_data_list = load_json_from_file(COURSE_DATA_PATH)

        fake_courses = Course.objects.filter(description__startswith=FAKE_COURSE_DESC_PREFIX).all()
        if fake_courses.count() > 0:
            self.stdout.write("Seed data appears to already exist. Going to update the dates of the existing courses.")
        else:
                fake_courses = deserialize_course_data_list(course_data_list)

