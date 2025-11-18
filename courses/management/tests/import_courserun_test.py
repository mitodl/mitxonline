"""Tests for import_courserun management command"""

from unittest.mock import Mock

import pytest

from b2b.factories import ContractPageFactory
from courses.factories import (
    CourseFactory,
    DepartmentFactory,
    ProgramFactory,
)
from courses.management.commands import import_courserun

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def mock_edx_course_detail():
    """Mock edX course detail response"""
    mock_course = Mock()
    mock_course.course_id = "course-v1:MITx+6.00x+2023_Fall"
    mock_course.name = "Introduction to Computer Science"
    mock_course.start = "2023-09-01T00:00:00Z"
    mock_course.end = "2023-12-15T00:00:00Z"
    mock_course.enrollment_start = "2023-08-01T00:00:00Z"
    mock_course.enrollment_end = "2023-09-15T00:00:00Z"
    mock_course.is_self_paced.return_value = False
    return mock_course


@pytest.fixture
def mock_edx_api_client(mock_edx_course_detail):
    """Mock edX API client"""
    mock_client = Mock()
    mock_client.get_detail.return_value = mock_edx_course_detail
    return mock_client


@pytest.fixture
def department():
    """Create a department for testing"""
    return DepartmentFactory.create(name="Computer Science")


@pytest.fixture
def program_with_courses():
    """Create a program with courses for testing"""
    program = ProgramFactory.create(readable_id="program-v1:MITx+CS")
    course1 = CourseFactory.create(readable_id="course-v1:MITx+6.00x")
    course2 = CourseFactory.create(readable_id="course-v1:MITx+6.001x")
    program.add_requirement(course1)
    program.add_requirement(course2)
    return program


class TestImportCourserunCommand:
    """Test cases for the import_courserun command"""

    def test_program_without_run_tag(self, mocker, program_with_courses):
        """Test that providing program without run_tag does nothing"""
        # Mock the API client to prevent it from being initialized
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client"
        )

        command = import_courserun.Command()
        result = command.handle(program=str(program_with_courses.id))
        assert result is None

    def test_run_tag_without_program(self, mocker):
        """Test that providing run_tag without program does nothing"""
        # Mock the API client to prevent it from being initialized
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client"
        )

        command = import_courserun.Command()
        result = command.handle(run_tag="2023_Fall")
        assert result is None

    @pytest.mark.parametrize(
        ("publish_cms_page", "draft_cms_page", "expected_error"),
        [
            (True, True, True),
            (True, False, False),
            (False, True, False),
            (False, False, False),
        ],
    )
    def test_cms_page_flag_validation(
        self, mocker, publish_cms_page, draft_cms_page, expected_error
    ):
        """Test validation of mutually exclusive CMS page flags"""
        # Mock the API client to prevent it from being initialized
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client"
        )

        command = import_courserun.Command()
        result = command.handle(
            publish_cms_page=publish_cms_page, draft_cms_page=draft_cms_page
        )

        if expected_error:
            assert result is False
        else:
            assert result is None

    def test_resolve_contract_by_id(self):
        """Test resolving contract by numeric ID"""
        contract = ContractPageFactory.create()
        command = import_courserun.Command()

        resolved = command._resolve_contract(str(contract.id))  # noqa: SLF001
        assert resolved == contract

    def test_resolve_contract_by_slug(self):
        """Test resolving contract by slug"""
        contract = ContractPageFactory.create()
        command = import_courserun.Command()

        resolved = command._resolve_contract(contract.slug)  # noqa: SLF001
        assert resolved == contract

    def test_resolve_contract_not_found(self):
        """Test handling of non-existent contract"""
        command = import_courserun.Command()

        resolved = command._resolve_contract("nonexistent")  # noqa: SLF001
        assert resolved is None

    def test_resolve_contract_none_identifier(self):
        """Test resolving contract with None identifier"""
        command = import_courserun.Command()
        resolved = command._resolve_contract(None)  # noqa: SLF001
        assert resolved is None

    def test_contract_validation_failure(self, mocker):
        """Test handling of invalid contract"""
        # Mock the API client to prevent it from being initialized
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client"
        )

        command = import_courserun.Command()
        result = command.handle(contract="nonexistent-contract")
        assert result is False
