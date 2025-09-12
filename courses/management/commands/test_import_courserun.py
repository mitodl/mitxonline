"""Tests for import_courserun management command"""

import pytest
from decimal import Decimal
from unittest.mock import Mock

from courses.factories import (
    CourseFactory,
    DepartmentFactory,
    ProgramFactory,
    CourseRunFactory,
)
from courses.management.commands import import_courserun
from courses.models import Course, CourseRun, BlockedCountry
from ecommerce.models import Product
from django.contrib.contenttypes.models import ContentType

from b2b.factories import ContractPageFactory

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
        ]
    )
    def test_cms_page_flag_validation(self, mocker, publish_cms_page, draft_cms_page, expected_error):
        """Test validation of mutually exclusive CMS page flags"""
        # Mock the API client to prevent it from being initialized
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client"
        )

        command = import_courserun.Command()
        result = command.handle(
            publish_cms_page=publish_cms_page,
            draft_cms_page=draft_cms_page
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

    def test_no_departments_provided(self, mocker, mock_edx_api_client):
        """Test that command fails when no departments are provided"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )

        command = import_courserun.Command()
        result = command.handle(courserun="course-v1:MITx+6.00x+2023_Fall")
        assert result is False

    def test_nonexistent_departments(self, mocker, mock_edx_api_client):
        """Test that command fails when specified departments don't exist"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=["Nonexistent Department"]
        )
        assert result is False

    def test_edx_api_error_single_course(self, mocker, department):
        """Test handling of edX API error for single course"""
        mock_client = Mock()
        mock_client.get_detail.side_effect = Exception("API Error")
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_client
        )
        
        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name]
        )
        assert result is False

    def test_successful_courserun_creation(self, mocker, mock_edx_api_client, mock_edx_course_detail, department):
        """Test successful creation of a course run"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")
        
        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            live=True
        )
        
        assert result is None
        
        # Verify course was created
        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        assert course.title == mock_edx_course_detail.name
        assert course.live is True
        assert department in course.departments.all()
        
        # Verify course run was created
        course_run = CourseRun.objects.get(courseware_id="course-v1:MITx+6.00x+2023_Fall")
        assert course_run.course == course
        assert course_run.run_tag == "2023_Fall"
        assert course_run.title == mock_edx_course_detail.name
        assert course_run.live is True
        assert course_run.is_self_paced is False

    def test_existing_course_reuse(self, mocker, mock_edx_api_client, department):
        """Test that existing course is reused when creating new run"""
        # Create existing course
        existing_course = CourseFactory.create(readable_id="course-v1:MITx+6.00x")

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name]
        )

        assert result is None

        # Verify existing course was reused
        courses = Course.objects.filter(readable_id="course-v1:MITx+6.00x")
        assert courses.count() == 1
        assert courses.first() == existing_course

        # Verify departments were updated
        existing_course.refresh_from_db()
        assert department in existing_course.departments.all()

    def test_courserun_with_contract(self, mocker, mock_edx_api_client, department):
        """Test creating course run with B2B contract"""
        contract = ContractPageFactory.create()

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            contract=str(contract.id)
        )

        assert result is None

        # Verify course run was created with contract
        course_run = CourseRun.objects.get(courseware_id="course-v1:MITx+6.00x+2023_Fall")
        assert course_run.b2b_contract == contract

    def test_cms_page_creation_draft(self, mocker, mock_edx_api_client, department):
        """Test CMS page creation in draft mode"""
        mock_create_page = mocker.patch("courses.management.commands.import_courserun.create_default_courseware_page")
        mock_page = Mock()
        mock_create_page.return_value = mock_page

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            create_cms_page=True,
            draft_cms_page=True
        )

        assert result is None

        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        mock_create_page.assert_called_once_with(course, live=False)

    def test_cms_page_creation_live(self, mocker, mock_edx_api_client, department):
        """Test CMS page creation in live mode"""
        mock_create_page = mocker.patch("courses.management.commands.import_courserun.create_default_courseware_page")
        mock_page = Mock()
        mock_create_page.return_value = mock_page

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            create_cms_page=True,
            publish_cms_page=True
        )

        assert result is None

        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        mock_create_page.assert_called_once_with(course, live=True)

    def test_cms_page_creation_with_flags(self, mocker, mock_edx_api_client, department):
        """Test CMS page creation with catalog and AI flags"""
        mock_create_page = mocker.patch("courses.management.commands.import_courserun.create_default_courseware_page")
        mock_page = Mock()
        mock_page.include_in_learn_catalog = False
        mock_page.ingest_content_files_for_ai = False
        mock_create_page.return_value = mock_page

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            create_cms_page=True,
            include_in_learn_catalog=True,
            ingest_content_files_for_ai=True
        )

        assert result is None

        # Verify flags were set
        mock_page.save.assert_called_once()
        assert mock_page.include_in_learn_catalog is True
        assert mock_page.ingest_content_files_for_ai is True

    def test_product_creation(self, mocker, mock_edx_api_client, department):
        """Test product creation with price"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            price="99.50"
        )

        assert result is None

        # Verify product was created
        course_run = CourseRun.objects.get(courseware_id="course-v1:MITx+6.00x+2023_Fall")
        content_type = ContentType.objects.get_for_model(CourseRun)

        product = Product.objects.get(
            content_type=content_type,
            object_id=course_run.id
        )
        assert product.price == Decimal("99.50")
        assert product.description == course_run.courseware_id
        assert product.is_active is True

    def test_country_blocking_by_code(self, mocker, mock_edx_api_client, department):
        """Test blocking countries by ISO code"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            block_countries="US,CA,GB"
        )

        assert result is None

        # Verify blocked countries were created
        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        blocked_countries = BlockedCountry.objects.filter(course=course)

        country_codes = {bc.country for bc in blocked_countries}
        assert "US" in country_codes
        assert "CA" in country_codes
        assert "GB" in country_codes

    def test_invalid_country_blocking(self, mocker, mock_edx_api_client, department):
        """Test handling of invalid country codes/names"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            block_countries="US,InvalidCountry,CA"
        )

        assert result is None

        # Verify valid countries were blocked, invalid ignored
        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        blocked_countries = BlockedCountry.objects.filter(course=course)

        country_codes = {bc.country for bc in blocked_countries}
        assert "US" in country_codes
        assert "CA" in country_codes
        assert len(country_codes) == 2  # Invalid country should not be added

    def test_program_iteration_success(self, mocker, program_with_courses, department):
        """Test successful iteration through program courses"""
        # Mock edX API to return course details for each course in program
        mock_client = Mock()

        def mock_get_detail(course_id, username):
            if "6.00x" in course_id or "6.001x" in course_id:
                mock_course = Mock()
                mock_course.course_id = course_id
                mock_course.name = f"Course {course_id}"
                mock_course.start = "2023-09-01T00:00:00Z"
                mock_course.end = "2023-12-15T00:00:00Z"
                mock_course.enrollment_start = "2023-08-01T00:00:00Z"
                mock_course.enrollment_end = "2023-09-15T00:00:00Z"
                mock_course.is_self_paced.return_value = False
                return mock_course
            return None

        mock_client.get_detail.side_effect = mock_get_detail

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            program=str(program_with_courses.id),
            run_tag="2023_Fall",
            depts=[department.name]
        )

        assert result is None

        # Verify course runs were created for both courses
        assert CourseRun.objects.filter(run_tag="2023_Fall").count() == 2

    def test_program_iteration_skip_existing(self, mocker, program_with_courses, department):
        """Test that existing course runs are skipped during program iteration"""
        # Create existing course run for one of the courses
        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        CourseRunFactory.create(course=course, run_tag="2023_Fall")
        
        mock_client = Mock()
        
        def mock_get_detail(course_id, username):
            if "6.001x" in course_id:
                mock_course = Mock()
                mock_course.course_id = course_id
                mock_course.name = f"Course {course_id}"
                mock_course.start = "2023-09-01T00:00:00Z"
                mock_course.end = "2023-12-15T00:00:00Z"
                mock_course.enrollment_start = "2023-08-01T00:00:00Z"
                mock_course.enrollment_end = "2023-09-15T00:00:00Z"
                mock_course.is_self_paced.return_value = False
                return mock_course
            return None  # Don't return data for 6.00x since it already exists
        
        mock_client.get_detail.side_effect = mock_get_detail
        
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")
        
        command = import_courserun.Command()
        result = command.handle(
            program=str(program_with_courses.id),
            run_tag="2023_Fall",
            depts=[department.name]
        )
        
        assert result is None
        
        # Should only create one new course run (6.001x), skip existing (6.00x)
        new_runs = CourseRun.objects.filter(run_tag="2023_Fall").count()
        assert new_runs == 2  # 1 existing + 1 newly created

    def test_program_by_readable_id(self, mocker, program_with_courses, department):
        """Test finding program by readable_id instead of numeric ID"""
        mock_client = Mock()
        mock_client.get_detail.return_value = None  # No courses found in edX
        
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_client
        )
        
        command = import_courserun.Command()
        result = command.handle(
            program=program_with_courses.readable_id,
            run_tag="2023_Fall",
            depts=[department.name]
        )
        
        assert result is None

    def test_program_not_found(self, mocker, department):
        """Test handling when program is not found"""
        mock_client = Mock()
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_client
        )
        
        command = import_courserun.Command()
        result = command.handle(
            program="nonexistent-program",
            run_tag="2023_Fall",
            depts=[department.name]
        )
        
        assert result is False

    def test_program_api_error(self, mocker, program_with_courses, department):
        """Test handling of API error during program iteration"""
        mock_client = Mock()
        mock_client.get_detail.side_effect = Exception("API Error")
        
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_client
        )
        
        command = import_courserun.Command()
        result = command.handle(
            program=str(program_with_courses.id),
            run_tag="2023_Fall",
            depts=[department.name]
        )
        
        assert result is None  # Command continues despite API errors

    def test_multiple_departments(self, mocker, mock_edx_api_client):
        """Test assigning multiple departments to a course"""
        dept1 = DepartmentFactory.create(name="Computer Science")
        dept2 = DepartmentFactory.create(name="Mathematics")

        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[dept1.name, dept2.name]
        )

        assert result is None

        # Verify both departments were assigned
        course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
        assert dept1 in course.departments.all()
        assert dept2 in course.departments.all()
        assert course.departments.count() == 2

    def test_non_numeric_price(self, mocker, mock_edx_api_client, department):
        """Test that non-numeric price doesn't create product"""
        mocker.patch(
            "courses.management.commands.import_courserun.get_edx_api_course_detail_client",
            return_value=mock_edx_api_client
        )
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_API_BASE_URL", "https://courses.example.com")
        mocker.patch("courses.management.commands.import_courserun.settings.OPENEDX_SERVICE_WORKER_USERNAME", "worker")

        command = import_courserun.Command()
        result = command.handle(
            courserun="course-v1:MITx+6.00x+2023_Fall",
            depts=[department.name],
            price="invalid"
        )

        assert result is None

        # Verify no product was created
        course_run = CourseRun.objects.get(courseware_id="course-v1:MITx+6.00x+2023_Fall")
        content_type = ContentType.objects.get_for_model(CourseRun)

        products = Product.objects.filter(
            content_type=content_type,
            object_id=course_run.id
        )
        assert products.count() == 0
