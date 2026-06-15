"""Tests for conftest."""

import pytest

from courses.models import CourseRun

pytestmark = [pytest.mark.django_db]


def test_b2b_courses_fixture(course_catalog_data, b2b_courses):
    """
    The b2b_courses fixture should create a number of source runs and runs for
    each contract, which should be added onto in addition to the regular runs
    that the course_catalog_data fixture creates.
    """

    courses, *_ = course_catalog_data
    orgs, contracts_by_org, b2b_runs, runs_by_contract, runs_by_org = b2b_courses

    # Make sure the b2b runs exist in the courses

    expected_course_ids = [r.id for r in courses]
    b2b_run_course_ids = []
    b2b_run_course_ids = [
        r.id for r in b2b_runs if r.course_id not in b2b_run_course_ids
    ]

    assert expected_course_ids.sort() == b2b_run_course_ids.sort()

    # Check for source runs for the b2b runs.
    # These should be one-to-one with the contract runs that exist.

    assert CourseRun.objects.filter(
        course_id__in=b2b_run_course_ids, is_source_run=True
    ).count() == len(b2b_run_course_ids)

    # Make sure each contract has

    for org in orgs:
        contracts = contracts_by_org[org.id]
