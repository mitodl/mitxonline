"""Tests for B2B tasks."""

import pytest
from mitol.common.utils import now_in_utc
from opaque_keys.edx.keys import CourseKey

from b2b.constants import B2B_RUN_TAG_FORMAT
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.tasks import create_program_contract_runs
from courses.constants import UAI_COURSEWARE_ID_PREFIX
from courses.factories import CourseFactory, CourseRunFactory, ProgramFactory
from courses.models import ProgramRequirement, ProgramRequirementNodeType

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


def test_create_program_contract_runs_success(mocker):
    """Test successful creation of contract runs for a program."""
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course1 = CourseFactory.create()
    course2 = CourseFactory.create()

    add_courses_to_program(program, [course1, course2])

    CourseRunFactory.create(
        course=course1,
        is_source_run=True,
        courseware_id="course-v1:MITx+course1+SOURCE",
    )
    CourseRunFactory.create(
        course=course2, run_tag="SOURCE", courseware_id="course-v1:MITx+course2+SOURCE"
    )

    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")

    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")

    mock_task = mocker.Mock()
    mock_task.request.id = "test-task-id"

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    assert mock_create_contract_run.call_count == 2
    mock_create_contract_run.assert_any_call(contract, course1)
    mock_create_contract_run.assert_any_call(contract, course2)

    expected_lock_key = f"create_program_contract_runs_lock:{contract.id}:{program.id}"
    mock_cache_add.assert_called_once()
    mock_cache_delete.assert_called_once_with(expected_lock_key)


def test_create_program_contract_runs_lock_not_acquired(mocker):
    """Test task skips execution when lock cannot be acquired."""

    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()

    mocker.patch("django.core.cache.cache.add", return_value=False)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_info = mocker.patch("b2b.tasks.log.info")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    mock_log_info.assert_called_once_with(
        "Task already running for contract %s and program %s, skipping duplicate",
        contract.id,
        program.id,
    )
    mock_create_contract_run.assert_not_called()
    mock_cache_delete.assert_not_called()


def test_create_program_contract_runs_skips_existing_runs(mocker):
    """Test that existing contract runs are skipped."""
    organization = OrganizationPageFactory.create(org_key="TEST")
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])

    source_run = CourseRunFactory.create(
        course=course,
        is_source_run=True,
        courseware_id="course-v1:MITx+testcourse+SOURCE",
    )

    current_year = now_in_utc().year
    new_run_tag = B2B_RUN_TAG_FORMAT.format(year=current_year, contract_id=contract.id)
    source_id = CourseKey.from_string(source_run.courseware_id)
    existing_courseware_id = f"{UAI_COURSEWARE_ID_PREFIX}{organization.org_key}+{source_id.course}+{new_run_tag}"

    CourseRunFactory.create(course=course, courseware_id=existing_courseware_id)

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_debug = mocker.patch("b2b.tasks.log.debug")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    mock_create_contract_run.assert_not_called()
    mock_log_debug.assert_called_once_with(
        "Contract run already exists for course %s in contract %s",
        course.readable_id,
        contract.slug,
    )


def test_create_program_contract_runs_courses_without_source_runs(mocker):
    """Test handling of courses without source runs."""

    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()

    course_with_source = CourseFactory.create()
    CourseRunFactory.create(
        course=course_with_source,
        is_source_run=True,
        courseware_id="course-v1:MITx+course1+SOURCE",
    )

    course_without_source = CourseFactory.create()
    CourseRunFactory.create(
        course=course_without_source, is_source_run=False, run_tag="REGULAR"
    )

    add_courses_to_program(program, [course_with_source, course_without_source])

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_info = mocker.patch("b2b.tasks.log.info")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    mock_create_contract_run.assert_called_once_with(contract, course_with_source)

    final_log_call = mock_log_info.call_args_list[-1]
    assert "Completed contract run creation" in final_log_call[0][0]

    assert final_log_call[0][5] == 1


def test_create_program_contract_runs_no_source_runs_for_course(mocker):
    """Test handling when a course has no valid source run."""

    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])

    CourseRunFactory.create(course=course, is_source_run=False, run_tag="REGULAR")

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    mock_create_contract_run.assert_not_called()


def test_create_program_contract_runs_clears_cached_requirements_data(mocker):
    """Test that cached requirements data is cleared from the program."""
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])

    CourseRunFactory.create(
        course=course, is_source_run=True, courseware_id="course-v1:MITx+course+SOURCE"
    )

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    _mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    _mock_create_contract_run.assert_called_once()


def test_create_program_contract_runs_exception_releases_lock(mocker):
    """Test that lock is released even when an exception occurs."""
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")

    mock_get_contract = mocker.patch("b2b.models.ContractPage.objects.get")
    mock_get_contract.side_effect = Exception("Database error")

    try:
        result = create_program_contract_runs.apply(
            args=[contract.id, program.id],
            kwargs={},
        )
        assert not result.successful()
    except Exception:
        pass

    expected_lock_key = f"create_program_contract_runs_lock:{contract.id}:{program.id}"
    mock_cache_delete.assert_called_once_with(expected_lock_key)


def test_create_program_contract_runs_source_run_by_tag(mocker):
    """Test finding source run by 'SOURCE' tag when is_source_run is False."""
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])

    CourseRunFactory.create(
        course=course,
        is_source_run=False,
        run_tag="SOURCE",
        courseware_id="course-v1:MITx+testcourse+SOURCE",
    )

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    mock_create_contract_run.assert_called_once_with(contract, course)


def test_create_program_contract_runs_mixed_source_run_types(mocker):
    """Test handling programs with mix of is_source_run=True and run_tag='SOURCE' courses."""

    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()

    course1 = CourseFactory.create()
    course2 = CourseFactory.create()
    add_courses_to_program(program, [course1, course2])

    CourseRunFactory.create(
        course=course1,
        is_source_run=True,
        courseware_id="course-v1:MITx+course1+SOURCE",
    )

    CourseRunFactory.create(
        course=course2,
        is_source_run=False,
        run_tag="SOURCE",
        courseware_id="course-v1:MITx+course2+SOURCE",
    )

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()
    assert mock_create_contract_run.call_count == 2
    mock_create_contract_run.assert_any_call(contract, course1)
    mock_create_contract_run.assert_any_call(contract, course2)


def test_create_program_contract_runs_logging_output(mocker):
    """Test that appropriate log messages are generated."""
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])

    CourseRunFactory.create(
        course=course, is_source_run=True, courseware_id="course-v1:MITx+course+SOURCE"
    )

    mocker.patch("django.core.cache.cache.add", return_value=True)
    mocker.patch("django.core.cache.cache.delete")
    mocker.patch("b2b.api.create_contract_run")
    mock_log_info = mocker.patch("b2b.tasks.log.info")

    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )

    assert result.successful()

    assert any(
        "Created contract run for course" in str(call)
        for call in mock_log_info.call_args_list
    )

    final_call = mock_log_info.call_args_list[-1]
    assert "Completed contract run creation" in final_call[0][0]

    assert final_call[0][1] == program.readable_id
    assert final_call[0][2] == contract.slug
    assert final_call[0][3] == 1
    assert final_call[0][4] == 0
    assert final_call[0][5] == 0
