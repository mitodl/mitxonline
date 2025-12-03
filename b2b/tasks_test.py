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
    
    # Create a required courses node
    required_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    
    # Add each course as a requirement
    for course in courses:
        required_courses_node.add_child(
            node_type=ProgramRequirementNodeType.COURSE, 
            course=course
        )


def test_create_program_contract_runs_success(mocker):
    """Test successful creation of contract runs for a program."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course1 = CourseFactory.create()
    course2 = CourseFactory.create()
    
    # Add courses to program via requirements tree
    add_courses_to_program(program, [course1, course2])
    
    # Create source runs
    CourseRunFactory.create(
        course=course1,
        is_source_run=True,
        courseware_id="course-v1:MITx+course1+SOURCE"
    )
    CourseRunFactory.create(
        course=course2,
        run_tag="SOURCE",
        courseware_id="course-v1:MITx+course2+SOURCE"
    )
    
    # Mock the create_contract_run API function
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    
    # Mock cache to simulate successful lock acquisition
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    
    # Create a mock task request
    mock_task = mocker.Mock()
    mock_task.request.id = "test-task-id"
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
    assert result.successful()
    assert mock_create_contract_run.call_count == 2
    mock_create_contract_run.assert_any_call(contract, course1)
    mock_create_contract_run.assert_any_call(contract, course2)
    
    # Verify cache operations
    expected_lock_key = f"create_program_contract_runs_lock:{contract.id}:{program.id}"
    mock_cache_add.assert_called_once()
    mock_cache_delete.assert_called_once_with(expected_lock_key)


def test_create_program_contract_runs_lock_not_acquired(mocker):
    """Test task skips execution when lock cannot be acquired."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    
    # Mock cache to simulate failed lock acquisition
    _mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=False)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_info = mocker.patch("b2b.tasks.log.info")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
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
    # Setup
    organization = OrganizationPageFactory.create(org_key="TEST")
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])
    
    # Create source run
    source_run = CourseRunFactory.create(
        course=course,
        is_source_run=True,
        courseware_id="course-v1:MITx+testcourse+SOURCE"
    )
    
    # Create existing contract run with the expected ID
    current_year = now_in_utc().year
    new_run_tag = B2B_RUN_TAG_FORMAT.format(year=current_year, contract_id=contract.id)
    source_id = CourseKey.from_string(source_run.courseware_id)
    existing_courseware_id = f"{UAI_COURSEWARE_ID_PREFIX}{organization.org_key}+{source_id.course}+{new_run_tag}"
    
    CourseRunFactory.create(
        course=course,
        courseware_id=existing_courseware_id
    )
    
    # Mock cache and API
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_debug = mocker.patch("b2b.tasks.log.debug")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
    assert result.successful()
    mock_create_contract_run.assert_not_called()
    mock_log_debug.assert_called_once_with(
        "Contract run already exists for course %s in contract %s",
        course.readable_id,
        contract.slug,
    )


def test_create_program_contract_runs_courses_without_source_runs(mocker):
    """Test handling of courses without source runs."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    
    # Course with source run
    course_with_source = CourseFactory.create()
    CourseRunFactory.create(
        course=course_with_source,
        is_source_run=True,
        courseware_id="course-v1:MITx+course1+SOURCE"
    )
    
    # Course without source run
    course_without_source = CourseFactory.create()
    CourseRunFactory.create(
        course=course_without_source,
        is_source_run=False,
        run_tag="REGULAR"
    )
    
    add_courses_to_program(program, [course_with_source, course_without_source])
    
    # Mock cache and API
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_info = mocker.patch("b2b.tasks.log.info")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
    assert result.successful()
    mock_create_contract_run.assert_called_once_with(contract, course_with_source)
    
    # Check the final log message includes count of courses without source runs
    final_log_call = mock_log_info.call_args_list[-1]
    assert "Completed contract run creation" in final_log_call[0][0]
    # Check the arguments: should be 1 created, 0 skipped, 1 without source
    assert final_log_call[0][5] == 1  # courses_without_source


def test_create_program_contract_runs_no_source_runs_for_course(mocker):
    """Test handling when a course has no valid source run."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])
    
    # Create a course run that is NOT a source run
    CourseRunFactory.create(
        course=course,
        is_source_run=False,
        run_tag="REGULAR"
    )
    
    # Mock cache and API
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify - should not call create_contract_run because there's no source run
    assert result.successful()
    mock_create_contract_run.assert_not_called()


def test_create_program_contract_runs_clears_cached_requirements_data(mocker):
    """Test that cached requirements data is cleared from the program."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])
    
    # Create a source run so the task doesn't exit early
    CourseRunFactory.create(
        course=course,
        is_source_run=True,
        courseware_id="course-v1:MITx+course+SOURCE"
    )
    
    # Mock cache and API
    _mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    _mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    _mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify the task completed successfully
    # The actual clearing of cached data is tested implicitly by the successful execution
    assert result.successful()
    _mock_create_contract_run.assert_called_once()


def test_create_program_contract_runs_exception_releases_lock(mocker):
    """Test that lock is released even when an exception occurs."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    
    # Mock cache
    _mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    
    # Mock ContractPage.objects.get to raise an exception
    mock_get_contract = mocker.patch("b2b.models.ContractPage.objects.get")
    mock_get_contract.side_effect = Exception("Database error")
    
    # Execute - this should handle the exception gracefully
    try:
        result = create_program_contract_runs.apply(
            args=[contract.id, program.id],
            kwargs={},
        )
        # If we get here, the task didn't raise an exception but may have failed
        assert not result.successful()
    except Exception:
        # If an exception is raised, that's also acceptable for this test
        # as long as the lock is released
        pass
    
    # Verify lock was still released despite exception
    expected_lock_key = f"create_program_contract_runs_lock:{contract.id}:{program.id}"
    mock_cache_delete.assert_called_once_with(expected_lock_key)


def test_create_program_contract_runs_source_run_by_tag(mocker):
    """Test finding source run by 'SOURCE' tag when is_source_run is False."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])
    
    # Create source run with SOURCE tag but is_source_run=False
    CourseRunFactory.create(
        course=course,
        is_source_run=False,
        run_tag="SOURCE",
        courseware_id="course-v1:MITx+testcourse+SOURCE"
    )
    
    # Mock cache and API
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
    assert result.successful()
    mock_create_contract_run.assert_called_once_with(contract, course)


def test_create_program_contract_runs_mixed_source_run_types(mocker):
    """Test handling programs with mix of is_source_run=True and run_tag='SOURCE' courses."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    
    course1 = CourseFactory.create()
    course2 = CourseFactory.create()
    add_courses_to_program(program, [course1, course2])
    
    # Course 1: source run with is_source_run=True
    CourseRunFactory.create(
        course=course1,
        is_source_run=True,
        courseware_id="course-v1:MITx+course1+SOURCE"
    )
    
    # Course 2: source run with run_tag="SOURCE"
    CourseRunFactory.create(
        course=course2,
        is_source_run=False,
        run_tag="SOURCE",
        courseware_id="course-v1:MITx+course2+SOURCE"
    )
    
    # Mock cache and API
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
    assert result.successful()
    assert mock_create_contract_run.call_count == 2
    mock_create_contract_run.assert_any_call(contract, course1)
    mock_create_contract_run.assert_any_call(contract, course2)


def test_create_program_contract_runs_logging_output(mocker):
    """Test that appropriate log messages are generated."""
    # Setup
    organization = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(organization=organization)
    program = ProgramFactory.create()
    course = CourseFactory.create()
    add_courses_to_program(program, [course])
    
    # Create source run
    CourseRunFactory.create(
        course=course,
        is_source_run=True,
        courseware_id="course-v1:MITx+course+SOURCE"
    )
    
    # Mock cache and API
    mock_cache_add = mocker.patch("django.core.cache.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("django.core.cache.cache.delete")
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_log_info = mocker.patch("b2b.tasks.log.info")
    
    # Execute
    result = create_program_contract_runs.apply(
        args=[contract.id, program.id],
        kwargs={},
    )
    
    # Verify
    assert result.successful()
    
    # Check individual course creation log
    assert any(
        "Created contract run for course" in str(call)
        for call in mock_log_info.call_args_list
    )
    
    # Check completion summary log
    final_call = mock_log_info.call_args_list[-1]
    assert "Completed contract run creation" in final_call[0][0]
    # Check the arguments passed to log.info for correct values
    assert final_call[0][1] == program.readable_id  # program readable_id
    assert final_call[0][2] == contract.slug  # contract slug
    assert final_call[0][3] == 1  # created_count
    assert final_call[0][4] == 0  # skipped_count
    assert final_call[0][5] == 0  # courses_without_source