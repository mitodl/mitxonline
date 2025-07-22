"""Tests for the fix_eligible_course_flags command."""

import pytest

from b2b.factories import ContractPageFactory
from courses.factories import CourseRunFactory, ProgramFactory
from courses.management.commands import fix_eligible_course_flags

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "page_published",
    [
        True,
        False,
    ],
)
def test_basic_eligible_course(page_published):
    """
    Test with the most basic eligible course (i.e. one without B2B complications)

    The flags default to False, so create a course with a regular course run and
    a marketing page. The command should set the ingestion flag and the catalog
    flag to page_published. (Only ingest if we're enrollable or have B2B runs
    regardless of marketing page, and only add to catalog if we have a published
    marketing page.)
    """

    run = CourseRunFactory.create()
    run.course.page.live = page_published
    run.course.page.save()

    assert not run.course.include_in_learn_catalog
    assert not run.course.ingest_content_files_for_ai

    fix_eligible_course_flags.Command().handle(dry_run=False)

    run.refresh_from_db()
    assert run.course.include_in_learn_catalog == page_published
    assert run.course.ingest_content_files_for_ai == page_published


@pytest.mark.parametrize(
    "page_published",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "include_regular_run",
    [
        True,
        False,
    ],
)
def test_b2b_course(page_published, include_regular_run):
    """
    Test with a B2B course.

    B2B courses should always have their ingestion flags turned on. But they
    should only be in the Learn catalog if there's a published marketing page
    *and* at least one regular course run.
    """

    contract = ContractPageFactory.create()

    run = CourseRunFactory.create(
        b2b_contract=contract,
    )
    run.course.page.live = page_published
    run.course.page.save()

    if include_regular_run:
        CourseRunFactory.create(
            course=run.course,
        )

    # these default to false, so they won't be set right here
    assert not run.course.include_in_learn_catalog
    assert not run.course.ingest_content_files_for_ai

    fix_eligible_course_flags.Command().handle(dry_run=False)

    run.refresh_from_db()
    assert run.course.include_in_learn_catalog == (
        page_published and include_regular_run
    )
    # this should _always_ be true if there's a B2B run
    assert run.course.ingest_content_files_for_ai


@pytest.mark.parametrize(
    "filter_count",
    [
        1,
        3,
    ],
)
def test_filter_by_course(filter_count):
    """Test that the course filtering works."""

    regular_courses = CourseRunFactory.create_batch(
        3,
    )

    for rcrun in regular_courses:
        rcrun.course.page.live = False
        rcrun.course.page.save()

    filter_courses = CourseRunFactory.create_batch(
        filter_count,
    )

    filters = []

    for courserun in filter_courses:
        courserun.course.page.live = True
        courserun.course.page.save()
        filters.append(courserun.course.readable_id)

    fix_eligible_course_flags.Command().handle(dry_run=False, course=filters)

    for courserun in regular_courses:
        course = courserun.course
        course.refresh_from_db()
        assert not course.include_in_learn_catalog
        assert not course.ingest_content_files_for_ai

    for courserun in filter_courses:
        course = courserun.course
        course.refresh_from_db()
        assert course.include_in_learn_catalog
        assert course.ingest_content_files_for_ai


def test_filter_by_program():
    """Test that the filtering by program works."""

    regular_courses = CourseRunFactory.create_batch(3)
    programs = ProgramFactory.create_batch(2)

    program_1_runs = CourseRunFactory.create_batch(2)

    for run in program_1_runs:
        run.course.page.live = True
        run.course.page.save()
        programs[0].add_requirement(run.course)

    program_2_runs = CourseRunFactory.create_batch(2)

    for run in program_2_runs:
        run.course.page.live = True
        run.course.page.save()
        programs[1].add_requirement(run.course)

    fix_eligible_course_flags.Command().handle(
        dry_run=False,
        program=[
            programs[0].readable_id,
        ],
    )

    for run in program_1_runs:
        course = run.course
        course.refresh_from_db()
        assert course.include_in_learn_catalog
        assert course.ingest_content_files_for_ai

    for run in [*program_2_runs, *regular_courses]:
        course = run.course
        course.refresh_from_db()
        assert not course.include_in_learn_catalog
        assert not course.ingest_content_files_for_ai
