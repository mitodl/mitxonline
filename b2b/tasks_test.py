"""Tests for B2B tasks."""

import pytest

from b2b.factories import ContractPageFactory
from b2b.tasks import (
    create_program_contract_runs,
    push_upgraded_enrollments_to_edx,
)
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from courses.models import CourseRun, ProgramRequirement, ProgramRequirementNodeType
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from variants.factories import (
    ContractSupportedVariantFactory,
    CourseSupportedVariantFactory,
)

pytestmark = [pytest.mark.django_db]


def add_courses_to_program(program, courses):
    """Helper function to add courses to a program via requirements tree."""
    root_node = program.requirements_root

    required_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )

    for course in courses:
        required_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, course=course
        )


@pytest.fixture(autouse=True)
def mocked_clone(mocker):
    """Keep contract run creation from queueing edX clones."""

    return mocker.patch("openedx.tasks.clone_courserun.delay")


@pytest.fixture
def mocked_lock(mocker):
    """Let the task take its lock without a cache."""

    mocker.patch("django.core.cache.cache.add", return_value=True)
    return mocker.patch("django.core.cache.cache.delete")


def lock_key(contract, program):
    """Return the task's lock key for a contract and program."""

    return f"create_program_contract_runs_lock:{contract.id}:{program.id}"


def create_course(*, language="en", **run_kwargs):
    """Create a course with one source run in the given language."""

    run_kwargs.setdefault("is_source_run", True)
    run = CourseRunFactory.create(
        language=language,
        is_primary_language=True,
        variant_industry="",
        variant_length="",
        **run_kwargs,
    )
    run.course.possible_variant_sets.update(language=language)
    return run.course


def add_hindi_variant(variant_factory, variant_object):
    """Give a course or contract a second, Hindi variant set."""

    return variant_factory.create(
        variant_object=variant_object,
        language="hi",
        variant_industry="",
        variant_length="",
        default_variant=False,
    )


def create_course_with_hindi_variant():
    """Create a course with English and Hindi variant sets and source runs."""

    course = create_course()
    add_hindi_variant(CourseSupportedVariantFactory, course)
    CourseRunFactory.create(
        course=course,
        is_source_run=True,
        language="hi",
        variant_industry="",
        variant_length="",
    )
    return course


def contract_runs(contract, course):
    """Return the contract's runs for a course."""

    return CourseRun.objects.filter(course=course, b2b_contract=contract)


@pytest.mark.parametrize(
    "run_kwargs",
    [{"is_source_run": True}, {"is_source_run": False, "run_tag": "SOURCE"}],
)
def test_create_program_contract_runs_success(mocked_lock, mocked_clone, run_kwargs):
    """Each course gets a contract run, however its source run is designated."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    courses = [create_course(**run_kwargs) for _ in range(2)]
    add_courses_to_program(program, courses)

    result = create_program_contract_runs.apply(args=[contract.id, program.id])

    assert result.successful()
    for course in courses:
        assert contract_runs(contract, course).count() == 1
    assert mocked_clone.call_count == len(courses)
    mocked_lock.assert_called_once_with(lock_key(contract, program))


@pytest.mark.usefixtures("mocked_lock")
def test_create_program_contract_runs_passes_the_org_prefix():
    """The org prefix the task is queued with ends up in the run's key."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    course = create_course()
    add_courses_to_program(program, [course])

    create_program_contract_runs.apply(
        args=[contract.id, program.id], kwargs={"org_prefix": "PFX-"}
    )

    run = contract_runs(contract, course).get()
    assert run.courseware_id.startswith(
        f"course-v1:PFX-{contract.organization.org_key}+"
    )


def test_create_program_contract_runs_lock_not_acquired(mocker):
    """A second task for the same contract and program does nothing."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    course = create_course()
    add_courses_to_program(program, [course])

    mocker.patch("django.core.cache.cache.add", return_value=False)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")

    result = create_program_contract_runs.apply(args=[contract.id, program.id])

    assert result.successful()
    assert not contract_runs(contract, course).exists()
    mock_cache_delete.assert_not_called()


@pytest.mark.usefixtures("mocked_lock")
def test_create_program_contract_runs_skips_existing_runs():
    """Running the task again does not create a second run for a course."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    course = create_course()
    add_courses_to_program(program, [course])

    create_program_contract_runs.apply(args=[contract.id, program.id])
    result = create_program_contract_runs.apply(args=[contract.id, program.id])

    assert result.successful()
    assert contract_runs(contract, course).count() == 1


@pytest.mark.usefixtures("mocked_lock")
def test_create_program_contract_runs_uses_the_contracts_variant_sets():
    """Runs are created for the contract's variant sets, not all the course has."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    course = create_course_with_hindi_variant()
    add_courses_to_program(program, [course])

    result = create_program_contract_runs.apply(args=[contract.id, program.id])

    assert result.successful()
    assert [run.language for run in contract_runs(contract, course)] == ["en"]


@pytest.mark.usefixtures("mocked_lock")
def test_create_program_contract_runs_adds_a_later_variant_set():
    """A variant set added after the first run still gets its run."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    course = create_course_with_hindi_variant()
    add_courses_to_program(program, [course])

    create_program_contract_runs.apply(args=[contract.id, program.id])
    add_hindi_variant(ContractSupportedVariantFactory, contract)
    result = create_program_contract_runs.apply(args=[contract.id, program.id])

    assert result.successful()
    assert sorted(run.language for run in contract_runs(contract, course)) == [
        "en",
        "hi",
    ]


@pytest.mark.usefixtures("mocked_lock")
def test_create_program_contract_runs_skips_courses_without_a_usable_source_run(
    mocker,
):
    """A course with no usable source run is skipped, and the rest still get runs."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    no_source = create_course(is_source_run=False, run_tag="REGULAR")
    other_variant = create_course(language="fr")
    usable = create_course()
    add_courses_to_program(program, [no_source, other_variant, usable])
    mock_log_info = mocker.patch("b2b.tasks.log.info")

    result = create_program_contract_runs.apply(args=[contract.id, program.id])

    assert result.successful()
    assert not contract_runs(contract, no_source).exists()
    assert not contract_runs(contract, other_variant).exists()
    assert contract_runs(contract, usable).count() == 1
    assert mock_log_info.call_args_list[-1].args[-2:] == (1, 2)


def test_create_program_contract_runs_exception_releases_lock(mocker, mocked_lock):
    """The lock is released even when the task fails."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    mocker.patch(
        "b2b.models.ContractPage.objects.get",
        side_effect=RuntimeError("Database error"),
    )

    with pytest.raises(RuntimeError):
        create_program_contract_runs.apply(args=[contract.id, program.id])

    mocked_lock.assert_called_once_with(lock_key(contract, program))


def test_push_upgraded_enrollments_to_edx(mocker):
    """Pushed enrollments are marked enrolled; failures are left for retry."""

    good, bad, already_done = CourseRunEnrollmentFactory.create_batch(
        3, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE, edx_enrolled=False
    )
    already_done.edx_enrolled = True
    already_done.save()

    def fake_enroll(user, runs, *, mode):
        if runs[0] == bad.run:
            raise ConnectionError

    mocked_enroll = mocker.patch(
        "openedx.api.enroll_in_edx_course_runs", side_effect=fake_enroll
    )

    push_upgraded_enrollments_to_edx([good.id, bad.id, already_done.id])

    assert mocked_enroll.call_count == 2
    mocked_enroll.assert_any_call(
        good.user, [good.run], mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    good.refresh_from_db()
    bad.refresh_from_db()
    assert good.edx_enrolled is True
    assert bad.edx_enrolled is False
