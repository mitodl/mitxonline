"""Tests for conftest."""

from math import ceil

import pytest
from django.db.models import Q

from courses.models import CourseRun

pytestmark = [pytest.mark.django_db]


def test_b2b_courses_fixture(course_catalog_data, b2b_courses):
    """
    Test that the b2b_courses fixture creates the additional data that we expect.

    3 orgs should be created, and 3 contracts per org should be created. Then,
    for each course returned by course_catalog_data, it should create a default
    source run for each course, then it should create 3 B2B-only variant source
    runs. Each contract should get variants for half of the courses that have been
    set up.
    """

    courses, *_ = course_catalog_data
    _, contracts_by_org, b2b_runs, runs_by_contract, runs_by_org = b2b_courses

    # Make sure the B2B runs exist in the existing courses (i.e. we don't have
    # even more courses than we started with)

    expected_course_ids = [r.id for r in courses]
    b2b_run_course_ids = []
    for r in b2b_runs:
        if r.course_id not in b2b_run_course_ids:
            b2b_run_course_ids.append(r.course_id)

    assert expected_course_ids.sort() == b2b_run_course_ids.sort()

    # Make sure the courses have source runs for the variants set up.

    course_sources = {}

    for course in courses:
        useful_variants = course.possible_variant_sets.filter(
            Q(b2b_only=True) | Q(default_variant=True)
        )
        assert useful_variants.count() == 4

        useful_variants = useful_variants.all()
        qset_filter = Q(
            language=useful_variants[0].language,
            variant_length=useful_variants[0].variant_length,
            variant_industry=useful_variants[0].variant_industry,
        )
        for variant in useful_variants[1:]:
            qset_filter = qset_filter | Q(
                language=variant.language,
                variant_length=variant.variant_length,
                variant_industry=variant.variant_industry,
            )

        srs = (
            CourseRun.all_objects.filter(course=course, is_source_run=True)
            .filter(qset_filter)
            .all()
        )
        assert len(srs) == 4
        course_sources[course.id] = srs

    # Make sure each contract's runs are in the courses we expect, and that
    # there's variant runs for each. (And check the aggregations.)

    for org in contracts_by_org:
        org_run_ids = [r.id for r in runs_by_org[org]]

        assert len(org_run_ids) > 0

        for contract in contracts_by_org[org]:
            contract_run_ids = [r.id for r in runs_by_contract[contract.id]]

            assert set(contract_run_ids).issubset(org_run_ids)

            contract_courses = (
                CourseRun.all_objects.filter(id__in=contract_run_ids)
                .values_list("course_id", flat=True)
                .distinct()
            )

            assert len(contract_courses) == ceil(len(courses) * 0.5)

            for course_id in contract_courses:
                assert (
                    CourseRun.all_objects.filter(
                        course_id=course_id, b2b_contract=contract
                    ).count()
                    == 4
                )
