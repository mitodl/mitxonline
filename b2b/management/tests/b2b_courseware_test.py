"""Tests for the b2b_courseware command."""

import pytest

from b2b.factories import ContractPageFactory
from b2b.management.commands import b2b_courseware
from courses.factories import CourseRunFactory, ProgramFactory

pytestmark = [pytest.mark.django_db]


def _create_usable_program():
    """Create a usable program with a handful of courses."""

    program = ProgramFactory.create()
    runs = CourseRunFactory.create_batch(4, is_source_run=True)

    [program.add_requirement(run.course) for run in runs[:2]]
    [program.add_elective(run.course) for run in runs[2:]]

    return program, runs


def _add_run_languages(run):
    """Add some language runs to the specified runs. Make the run specified "en"."""

    langs = (
        "fr",
        "sw",
    )

    run.language = "en"
    run.is_primary_language = True
    run.save()

    return [
        CourseRunFactory.create(
            course=run.course,
            courseware_id=f"{run.courseware_id}_{lang}",
            run_tag=run.run_tag,
            language=lang,
            is_primary_language=False,
            is_source_run=run.is_source_run,
            b2b_contract=run.b2b_contract,
            start_date=run.start_date,
            end_date=run.end_date,
            enrollment_start=run.enrollment_start,
            enrollment_end=run.enrollment_end,
            live=run.live,
        )
        for lang in langs
    ]


@pytest.fixture
def mock_clone_courserun(mocker):
    """Mock out the edX API call to clone the course run."""

    return mocker.patch("openedx.tasks.clone_courserun.delay")


@pytest.mark.parametrize(
    "try_reruns",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "no_create_runs",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "with_languages",
    [
        False,
        True,
    ],
)
def test_add_program(mock_clone_courserun, with_languages, no_create_runs, try_reruns):
    """
    Test that adding a program to a contract works as expected.

    This should add all the courses, and grab all the languages that are set up
    as well.
    """

    contract = ContractPageFactory.create()
    program, runs = _create_usable_program()
    command = b2b_courseware.Command()

    if with_languages:
        [_add_run_languages(run) for run in runs]

    command.handle(
        subcommand="add",
        contract=str(contract.id),
        courseware=str(program.readable_id),
        no_create_runs=no_create_runs,
        allow_reruns=True,
        force=False,
        can_import="",
        prefix="",
        make_code=False,
    )

    expected_run_count = 12 if with_languages else 4
    assert contract.get_course_runs().count() == expected_run_count

    if no_create_runs:
        mock_clone_courserun.assert_not_called()
    else:
        mock_clone_courserun.assert_called()

    # Try to re-run the program - depending on what try_runs is set to, there
    # either should or shouldn't be a new set of runs.

    command.handle(
        subcommand="add",
        contract=str(contract.id),
        courseware=str(program.readable_id),
        no_create_runs=no_create_runs,
        allow_reruns=try_reruns,
        force=False,
        can_import="",
        prefix="",
        make_code=False,
    )

    assert contract.get_course_runs().count() == expected_run_count * (
        2 if try_reruns else 1
    )


@pytest.mark.parametrize(
    "with_languages",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "no_create_runs",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize(
    "try_reruns",
    [
        True,
        False,
    ],
)
def test_add_course(mock_clone_courserun, with_languages, no_create_runs, try_reruns):
    """Test that adding a single course works as expected."""

    contract = ContractPageFactory.create()
    run = CourseRunFactory.create(
        is_source_run=True,
        language="en" if with_languages else "",
        is_primary_language=with_languages,
    )
    command = b2b_courseware.Command()

    if with_languages:
        _add_run_languages(run)

    command.handle(
        subcommand="add",
        contract=str(contract.id),
        courseware=str(run.course.readable_id),
        no_create_runs=no_create_runs,
        allow_reruns=True,
        force=False,
        can_import="",
        prefix="",
        make_code=False,
    )

    expected_run_count = 3 if with_languages else 1
    assert contract.get_course_runs().count() == expected_run_count

    if no_create_runs:
        mock_clone_courserun.assert_not_called()
    else:
        mock_clone_courserun.assert_called()

    # Try to re-run the course - depending on what try_runs is set to, there
    # either should or shouldn't be a new course run.

    command.handle(
        subcommand="add",
        contract=str(contract.id),
        courseware=str(run.course.readable_id),
        no_create_runs=no_create_runs,
        allow_reruns=try_reruns,
        force=False,
        can_import="",
        prefix="",
        make_code=False,
    )

    assert contract.get_course_runs().count() == expected_run_count * (
        2 if try_reruns else 1
    )


def test_add_courserun():
    """Test adding an extant courserun to a contract."""

    contract = ContractPageFactory.create()
    run = CourseRunFactory.create(b2b_contract=None)
    command = b2b_courseware.Command()

    command.handle(
        subcommand="add",
        contract=str(contract.id),
        courseware=str(run.courseware_id),
        no_create_runs=False,
        allow_reruns=True,
        force=False,
        can_import="",
        prefix="",
        make_code=False,
    )

    run.refresh_from_db()
    assert run.b2b_contract == contract


@pytest.mark.parametrize(
    "force",
    [
        True,
        False,
    ],
)
def test_add_courserun_existing_contract(force):
    """Test adding an extant courserun to a contract."""

    contract = ContractPageFactory.create()
    existing_contract = ContractPageFactory.create()
    run = CourseRunFactory.create(b2b_contract=existing_contract)
    command = b2b_courseware.Command()

    command.handle(
        subcommand="add",
        contract=str(contract.id),
        courseware=str(run.courseware_id),
        no_create_runs=False,
        allow_reruns=True,
        force=force,
        can_import="",
        prefix="",
        make_code=False,
    )

    run.refresh_from_db()
    assert run.b2b_contract == (contract if force else existing_contract)
