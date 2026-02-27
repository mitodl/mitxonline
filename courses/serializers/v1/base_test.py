import pytest

from courses.factories import CourseFactory, ProgramFactory
from courses.serializers.v1.base import BaseCourseSerializer, BaseProgramSerializer

pytestmark = [pytest.mark.django_db]


def test_base_program_serializer():
    """Test BaseProgramSerializer serialization"""
    program = ProgramFactory.create()
    data = BaseProgramSerializer(program).data
    assert data == {
        "title": program.title,
        "readable_id": program.readable_id,
        "id": program.id,
        "type": "program",
    }


def test_base_course_serializer():
    """Test CourseRun serialization"""
    course = CourseFactory.create()
    data = BaseCourseSerializer(course).data
    assert data == {
        "title": course.title,
        "readable_id": course.readable_id,
        "id": course.id,
        "type": "course",
    }
