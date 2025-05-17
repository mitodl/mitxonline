"""Courses API tests"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import factory
import pytest
import reversion
from django.core.exceptions import ValidationError
from edx_api.course_detail import CourseDetail, CourseDetails, CourseMode, CourseModes
from mitol.common.utils.datetime import now_in_utc
from requests import ConnectionError as RequestsConnectionError
from requests import HTTPError
from reversion.models import Version

from courses.api import (
    create_program_enrollments,
    create_run_enrollments,
    deactivate_run_enrollment,
    defer_enrollment,
    generate_course_run_certificates,
    generate_program_certificate,
    manage_course_run_certificate_access,
    manage_program_certificate_access,
    override_user_grade,
    process_course_run_grade_certificate,
    sync_course_mode,
    sync_course_runs,
)
from courses.constants import (
    ENROLL_CHANGE_STATUS_DEFERRED,
    ENROLL_CHANGE_STATUS_REFUNDED,
    ENROLL_CHANGE_STATUS_UNENROLLED,
)
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    ProgramCertificateFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
    ProgramRequirementFactory,
    program_with_empty_requirements,  # noqa: F401
    program_with_requirements,  # noqa: F401
)

# pylint: disable=redefined-outer-name
from courses.models import (
    CourseRunEnrollment,
    PaidCourseRun,
    ProgramCertificate,
    ProgramEnrollment,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from ecommerce.factories import LineFactory, OrderFactory, ProductFactory
from ecommerce.models import OrderStatus
from main.test_utils import MockHttpError
from openedx.constants import (
    EDX_DEFAULT_ENROLLMENT_MODE,
    EDX_ENROLLMENT_AUDIT_MODE,
    EDX_ENROLLMENT_VERIFIED_MODE,
)
from openedx.exceptions import (
    EdxApiEnrollErrorException,
    NoEdxApiAuthError,
    UnknownEdxApiEnrollException,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def dates():
    """Fixture that provides several dates"""
    now = now_in_utc()
    return SimpleNamespace(
        future_60_days=now + timedelta(days=60),
        future_30_days=now + timedelta(days=30),
        future_10_days=now + timedelta(days=10),
        now=now,
        past_10_days=now - timedelta(days=10),
        past_30_days=now - timedelta(days=30),
        past_60_days=now - timedelta(days=60),
    )


@pytest.fixture
def course():
    """Course object fixture"""
    return CourseFactory.create()


@pytest.fixture
def passed_grade_with_enrollment(user):
    """Fixture to produce a passed CourseRunGrade"""
    paid_enrollment = CourseRunEnrollmentFactory.create(
        user=user, enrollment_mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    return CourseRunGradeFactory.create(
        course_run=paid_enrollment.run,
        user=paid_enrollment.user,
        grade=0.50,
        passed=True,
    )


@pytest.fixture
def courses_api_logs(mocker):
    """Logger fixture for tasks"""
    return mocker.patch("courses.api.log")


@pytest.mark.parametrize(
    "enrollment_mode", [EDX_DEFAULT_ENROLLMENT_MODE, EDX_ENROLLMENT_VERIFIED_MODE]
)
def test_create_run_enrollments(
    mocker, user, enrollment_mode, django_capture_on_commit_callbacks
):
    """
    create_run_enrollments should call the edX API to create enrollments, create or reactivate local
    enrollment records, and notify enrolled users via email

    In addition, there should be a ProgramEnrollment for the program that the
    course belongs to.
    """
    num_runs = 3
    runs = CourseRunFactory.create_batch(num_runs)
    # Create an existing deactivate enrollment to test that it gets reactivated
    CourseRunEnrollmentFactory.create(
        user=user,
        run=runs[0],
        change_status=ENROLL_CHANGE_STATUS_REFUNDED,
        active=False,
    )
    patched_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")
    patched_send_enrollment_email = mocker.patch(
        "courses.api.mail_api.send_course_run_enrollment_email"
    )
    mocker.patch("courses.tasks.subscribe_edx_course_emails.delay")

    successful_enrollments, edx_request_success = create_run_enrollments(
        user, runs, mode=enrollment_mode
    )
    patched_edx_enroll.assert_called_once_with(
        user,
        runs,
        mode=enrollment_mode,
    )

    with django_capture_on_commit_callbacks(execute=True):
        assert patched_send_enrollment_email.call_count == num_runs
        assert edx_request_success is True
        assert len(successful_enrollments) == num_runs
        enrollments = CourseRunEnrollment.objects.order_by("run__id").all()
        for run, enrollment in zip(runs, enrollments):
            assert enrollment.change_status is None
            assert enrollment.active is True
            assert enrollment.edx_enrolled is True
            assert enrollment.edx_emails_subscription is True
            assert enrollment.run == run
            assert enrollment.enrollment_mode == enrollment_mode
            patched_send_enrollment_email.assert_any_call(enrollment)


@pytest.mark.parametrize("is_active", [True, False])
def test_create_run_enrollments_upgrade(
    mocker,
    user,
    is_active,
    program_with_empty_requirements,  # noqa: F811
):
    """
    create_run_enrollments should call the edX API to create/update enrollments, and set the enrollment mode properly
    in the event of an upgrade e.g a user moving from Audit to Verified mode

    In addition, tests to make sure there's a ProgramEnrollment for the course.
    """
    test_enrollment = CourseRunEnrollmentFactory.create(
        user=user,
        change_status=ENROLL_CHANGE_STATUS_REFUNDED,
        active=is_active,
        edx_enrolled=True,
    )
    program_with_empty_requirements.add_requirement(test_enrollment.run.course)
    patched_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")
    patched_send_enrollment_email = mocker.patch(
        "courses.api.mail_api.send_course_run_enrollment_email"
    )
    mocker.patch("courses.tasks.subscribe_edx_course_emails.delay")

    successful_enrollments, edx_request_success = create_run_enrollments(
        user, runs=[test_enrollment.run], mode=EDX_ENROLLMENT_VERIFIED_MODE
    )
    patched_edx_enroll.assert_called_once_with(
        user,
        [test_enrollment.run],
        mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )

    patched_send_enrollment_email.assert_called_once()
    assert edx_request_success is True
    test_enrollment.refresh_from_db()
    assert test_enrollment.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE
    assert ProgramEnrollment.objects.filter(
        user=user, program=program_with_empty_requirements
    ).exists()


def test_create_run_enrollments_multiple_programs(
    mocker,
    user,
    program_with_empty_requirements,  # noqa: F811
):
    """
    create_run_enrollments should enroll the user into any Programs which have the CourseRun's Course defined as a requirement or elective.

    In addition, tests to make sure there's a ProgramEnrollment for the course.
    """
    test_enrollment = CourseRunEnrollmentFactory.create(
        user=user,
        change_status=ENROLL_CHANGE_STATUS_REFUNDED,
        active=True,
        edx_enrolled=True,
    )
    program_with_empty_requirements.add_requirement(test_enrollment.run.course)
    program2 = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program2)
    root_node = program2.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=1,
        title="Elective Courses",
    )
    program2.add_requirement(test_enrollment.run.course)
    patched_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")  # noqa: F841
    patched_send_enrollment_email = mocker.patch(  # noqa: F841
        "courses.api.mail_api.send_course_run_enrollment_email"
    )
    mocker.patch("courses.tasks.subscribe_edx_course_emails.delay")

    create_run_enrollments(
        user, runs=[test_enrollment.run], mode=EDX_ENROLLMENT_VERIFIED_MODE
    )

    assert ProgramEnrollment.objects.filter(
        user=user, program=program_with_empty_requirements
    ).exists()
    assert ProgramEnrollment.objects.filter(user=user, program=program2).exists()


@pytest.mark.parametrize(
    "exception_cls", [NoEdxApiAuthError, HTTPError, RequestsConnectionError]
)
def test_create_run_enrollments_api_fail(mocker, user, exception_cls):
    """
    create_run_enrollments should log a message and still create local enrollment records when certain exceptions
    are raised if a flag is set to true

    In addition, a ProgramEnrollment should also be created.
    """
    patched_edx_enroll = mocker.patch(
        "courses.api.enroll_in_edx_course_runs", side_effect=exception_cls
    )
    patched_log_exception = mocker.patch("courses.api.log.exception")
    patched_send_enrollment_email = mocker.patch(
        "courses.api.mail_api.send_course_run_enrollment_email"
    )
    run = CourseRunFactory.create()
    successful_enrollments, edx_request_success = create_run_enrollments(
        user,
        [run],
        keep_failed_enrollments=True,
    )
    patched_edx_enroll.assert_called_once_with(
        user,
        [run],
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
    )
    patched_log_exception.assert_called_once()
    patched_send_enrollment_email.assert_not_called()
    assert len(successful_enrollments) == 1
    assert edx_request_success is False


@pytest.mark.parametrize("keep_failed_enrollments", [True, False])
@pytest.mark.parametrize(
    "exception_cls,inner_exception",  # noqa: PT006
    [
        [EdxApiEnrollErrorException, MockHttpError()],  # noqa: PT007
        [UnknownEdxApiEnrollException, Exception()],  # noqa: PT007
    ],
)
def test_create_run_enrollments_enroll_api_fail(  # noqa: PLR0913
    mocker,
    user,
    keep_failed_enrollments,
    exception_cls,
    inner_exception,
    program_with_empty_requirements,  # noqa: F811
):
    """
    create_run_enrollments should log a message and still create local enrollment records when an enrollment exception
    is raised if a flag is set to true
    """
    num_runs = 3
    runs = CourseRunFactory.create_batch(num_runs)
    patched_edx_enroll = mocker.patch(
        "courses.api.enroll_in_edx_course_runs",
        side_effect=exception_cls(user, runs[2], inner_exception),
    )
    patched_log_exception = mocker.patch("courses.api.log.exception")
    patched_send_enrollment_email = mocker.patch(
        "courses.api.mail_api.send_course_run_enrollment_email"
    )

    successful_enrollments, edx_request_success = create_run_enrollments(
        user,
        runs,
        keep_failed_enrollments=keep_failed_enrollments,
    )
    patched_edx_enroll.assert_called_once_with(
        user,
        runs,
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
    )
    patched_log_exception.assert_called_once()
    patched_send_enrollment_email.assert_not_called()
    expected_enrollments = 0 if not keep_failed_enrollments else num_runs
    assert len(successful_enrollments) == expected_enrollments
    assert edx_request_success is False


def test_create_run_enrollments_creation_fail(mocker, user):
    """
    create_run_enrollments should log a message and send an admin email if there's an error during the
    creation of local enrollment records
    """
    runs = CourseRunFactory.create_batch(2)
    enrollment = CourseRunEnrollmentFactory.create(run=runs[1])
    mocker.patch(
        "courses.api.CourseRunEnrollment.all_objects.get_or_create",
        side_effect=[Exception(), (enrollment, True)],
    )
    patched_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")
    patched_log_exception = mocker.patch("courses.api.log.exception")
    patched_mail_api = mocker.patch("courses.api.mail_api")

    successful_enrollments, edx_request_success = create_run_enrollments(
        user,
        runs,
    )
    patched_edx_enroll.assert_called_once_with(
        user,
        runs,
        mode=EDX_DEFAULT_ENROLLMENT_MODE,
    )
    patched_log_exception.assert_called_once()
    patched_mail_api.send_course_run_enrollment_email.assert_not_called()
    patched_mail_api.send_enrollment_failure_message.assert_called_once()
    assert successful_enrollments == [enrollment]
    assert edx_request_success is True


def test_create_program_enrollments(user):
    """
    create_program_enrollments should create or reactivate local enrollment records
    """
    num_programs = 2
    programs = ProgramFactory.create_batch(num_programs)
    # Create an existing deactivate enrollment to test that it gets reactivated
    ProgramEnrollmentFactory.create(
        user=user,
        program=programs[0],
        change_status=ENROLL_CHANGE_STATUS_REFUNDED,
        active=False,
    )

    successful_enrollments = create_program_enrollments(
        user,
        programs,
    )
    assert len(successful_enrollments) == num_programs
    enrollments = ProgramEnrollment.objects.order_by("program__id").all()
    assert len(enrollments) == len(programs)
    for program, enrollment in zip(programs, enrollments):
        assert enrollment.change_status is None
        assert enrollment.active is True
        assert enrollment.program == program


def test_create_program_enrollments_creation_fail(mocker, user):
    """
    create_program_enrollments should log a message and send an admin email if there's an error during the
    creation of local enrollment records
    """
    programs = ProgramFactory.create_batch(2)
    enrollment = ProgramEnrollmentFactory.build(program=programs[1])
    mocker.patch(
        "courses.api.ProgramEnrollment.all_objects.get_or_create",
        side_effect=[Exception(), (enrollment, True)],
    )
    patched_log_exception = mocker.patch("courses.api.log.exception")
    patched_mail_api = mocker.patch("courses.api.mail_api")

    successful_enrollments = create_program_enrollments(
        user,
        programs,
    )
    patched_log_exception.assert_called_once()
    patched_mail_api.send_enrollment_failure_message.assert_called_once()
    assert successful_enrollments == [enrollment]


class TestDeactivateEnrollments:
    """Test cases for functions that deactivate enrollments"""

    @pytest.fixture
    def patches(self, mocker):  # pylint: disable=missing-docstring
        edx_unenroll = mocker.patch("courses.api.unenroll_edx_course_run")
        send_unenrollment_email = mocker.patch(
            "courses.api.mail_api.send_course_run_unenrollment_email"
        )
        sync_hubspot_line_by_line_id = mocker.patch(
            "hubspot_sync.task_helpers.sync_hubspot_line_by_line_id"
        )
        log_exception = mocker.patch("courses.api.log.exception")
        return SimpleNamespace(
            edx_unenroll=edx_unenroll,
            send_unenrollment_email=send_unenrollment_email,
            log_exception=log_exception,
            sync_hubspot_line_by_line_id=sync_hubspot_line_by_line_id,
        )

    def test_deactivate_run_enrollment(self, patches):
        """
        deactivate_run_enrollment should attempt to unenroll a user in a course run in edX and set the
        local enrollment record to inactive
        """
        enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
        with reversion.create_revision():
            product = ProductFactory.create(purchasable_object=enrollment.run)
        version = Version.objects.get_for_object(product).first()
        order = OrderFactory.create(
            state=OrderStatus.PENDING, purchaser=enrollment.user
        )
        LineFactory.create(
            order=order, purchased_object=enrollment.run, product_version=version
        )

        returned_enrollment = deactivate_run_enrollment(
            enrollment, change_status=ENROLL_CHANGE_STATUS_REFUNDED
        )
        patches.edx_unenroll.assert_called_once_with(enrollment)
        patches.send_unenrollment_email.assert_called_once_with(enrollment)
        patches.sync_hubspot_line_by_line_id.assert_called_once()
        enrollment.refresh_from_db()
        assert enrollment.change_status == ENROLL_CHANGE_STATUS_REFUNDED
        assert enrollment.active is False
        assert enrollment.edx_enrolled is False
        assert enrollment.edx_emails_subscription is False
        assert returned_enrollment == enrollment

    @pytest.mark.parametrize("keep_failed_enrollments", [True, False])
    def test_deactivate_run_enrollment_api_fail(self, patches, keep_failed_enrollments):
        """
        If a flag is provided, deactivate_run_enrollment should set local enrollment record to inactive even if the API call fails
        """
        enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)
        with reversion.create_revision():
            product = ProductFactory.create(purchasable_object=enrollment.run)
        version = Version.objects.get_for_object(product).first()
        order = OrderFactory.create(
            state=OrderStatus.PENDING, purchaser=enrollment.user
        )
        LineFactory.create(
            order=order, purchased_object=enrollment.run, product_version=version
        )
        patches.edx_unenroll.side_effect = Exception

        deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_REFUNDED,
            keep_failed_enrollments=keep_failed_enrollments,
        )
        if not keep_failed_enrollments:
            patches.sync_hubspot_line_by_line_id.assert_not_called()
        else:
            patches.sync_hubspot_line_by_line_id.assert_called_once()
        patches.edx_unenroll.assert_called_once_with(enrollment)
        patches.send_unenrollment_email.assert_not_called()
        patches.log_exception.assert_called_once()
        enrollment.refresh_from_db()
        assert enrollment.active is not keep_failed_enrollments

    def test_deactivate_run_enrollment_line_does_not_exist(
        self,
        patches,
    ):
        """
        If the enrollment does not have an associated Line object, don't call sync_line_item_with_hubspot()
        """
        enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)

        deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_REFUNDED,
        )
        patches.sync_hubspot_line_by_line_id.assert_not_called()


@pytest.mark.parametrize("keep_failed_enrollments", [True, False])
@pytest.mark.parametrize("edx_enroll_succeeds", [True, False])
@pytest.mark.parametrize("edx_downgrade_succeeds", [True, False])
@pytest.mark.parametrize("has_audit_enrollment_already", [True, False])

def test_defer_enrollment(
    mocker,
    course,
    keep_failed_enrollments,
    edx_enroll_succeeds,
    edx_downgrade_succeeds,
    has_audit_enrollment_already
):
    """
    defer_enrollment should downgrade current enrollment to audit and create a verified enrollment in another
    course run, and update PaidCourseRun to the new run
    """
    course_runs = CourseRunFactory.create_batch(3, course=course)
    existing_enrollment = CourseRunEnrollmentFactory.create(run=course_runs[0])
    fulfilled_order = OrderFactory.create(state=OrderStatus.FULFILLED)
    paid_course_run = PaidCourseRun.objects.create(
        user=existing_enrollment.user, course_run=course_runs[0], order=fulfilled_order
    )

    new_enrollment = CourseRunEnrollmentFactory.create(run=course_runs[1])
    audit_enrollment = None
    if has_audit_enrollment_already:
        audit_enrollment = CourseRunEnrollmentFactory.create(
            user=existing_enrollment.user,
            run=course_runs[1],
            enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE,
        )
    return_values = [
        ([new_enrollment] if edx_enroll_succeeds else [], edx_enroll_succeeds),
        (
            [existing_enrollment] if edx_downgrade_succeeds else [],
            edx_downgrade_succeeds,
        ),
    ]
    patched_deactivate_run_enrollment = mocker.patch(
        "courses.api.deactivate_run_enrollment",
        return_value=audit_enrollment,
    )
    with patch(
        "courses.api.create_run_enrollments", autospec=True
    ) as patched_create_enrollments:
        patched_create_enrollments.side_effect = return_values

        if keep_failed_enrollments or (edx_enroll_succeeds and edx_downgrade_succeeds):
            returned_from_enrollment, returned_to_enrollment = defer_enrollment(
                existing_enrollment.user,
                existing_enrollment.run.courseware_id,
                course_runs[1].courseware_id,
                keep_failed_enrollments=keep_failed_enrollments,
            )
            assert patched_create_enrollments.call_count == 2
            assert returned_from_enrollment == (
                existing_enrollment if edx_downgrade_succeeds else None
            )
            assert returned_to_enrollment == (
                new_enrollment if edx_enroll_succeeds else None
            )
            patched_create_enrollments.assert_has_calls(
                [
                    call(
                        user=existing_enrollment.user,
                        runs=[course_runs[1]],
                        change_status=None,
                        keep_failed_enrollments=keep_failed_enrollments,
                        mode=EDX_ENROLLMENT_VERIFIED_MODE,
                    ),
                    call(
                        user=existing_enrollment.user,
                        runs=[existing_enrollment.run],
                        change_status=ENROLL_CHANGE_STATUS_DEFERRED,
                        keep_failed_enrollments=keep_failed_enrollments,
                        mode=EDX_ENROLLMENT_AUDIT_MODE,
                    ),
                ]
            )
            paid_course_run.refresh_from_db()
            assert paid_course_run.course_run == course_runs[1]
        else:
            with pytest.raises(Exception):  # noqa: B017, PT011
                defer_enrollment(
                    existing_enrollment.user,
                    existing_enrollment.run.courseware_id,
                    course_runs[1].courseware_id,
                    keep_failed_enrollments=keep_failed_enrollments,
                )


def test_defer_enrollment_validation(mocker, user):
    """
    defer_enrollment should raise an exception if the 'from' or 'to' course runs are invalid
    """
    courses = CourseFactory.create_batch(2)
    enrollments = CourseRunEnrollmentFactory.create_batch(
        3,
        user=user,
        active=factory.Iterator([False, True, True]),
        run__course=factory.Iterator([courses[0], courses[0], courses[1]]),
    )
    unenrollable_run = CourseRunFactory.create(
        enrollment_end=now_in_utc() - timedelta(days=1)
    )
    patched_create_enrollments = mocker.patch(
        "courses.api.create_run_enrollments",
        return_value=([enrollments[0].run.courseware_id], True),
    )
    mocker.patch(
        "courses.api.deactivate_run_enrollment",
        return_value=enrollments[1],
    )

    with pytest.raises(ValidationError):
        # Deferring to the same course run should raise a validation error
        defer_enrollment(
            user, enrollments[0].run.courseware_id, enrollments[0].run.courseware_id
        )
    patched_create_enrollments.assert_not_called()

    with pytest.raises(ValidationError):
        # Deferring to a course run that is outside of its enrollment period should raise a validation error
        defer_enrollment(
            user, enrollments[0].run.courseware_id, unenrollable_run.courseware_id
        )
    patched_create_enrollments.assert_not_called()

    with pytest.raises(ValidationError):
        # Deferring from an inactive enrollment should raise a validation error
        defer_enrollment(
            user, enrollments[0].run.courseware_id, enrollments[1].run.courseware_id
        )
    patched_create_enrollments.assert_not_called()

    with pytest.raises(ValidationError):
        # Deferring to a course run in a different course should raise a validation error
        defer_enrollment(
            user, enrollments[1].run.courseware_id, enrollments[2].run.courseware_id
        )
    patched_create_enrollments.assert_not_called()

    # The last two cases should not raise an exception if the 'force' flag is set to True
    defer_enrollment(
        user,
        enrollments[0].run.courseware_id,
        enrollments[1].run.courseware_id,
        keep_failed_enrollments=True,
        force=True,
    )
    assert patched_create_enrollments.call_count == 2
    patched_create_enrollments.assert_has_calls(
        [
            call(
                user=user,
                runs=[enrollments[1].run],
                change_status=None,
                keep_failed_enrollments=True,
                mode=EDX_ENROLLMENT_VERIFIED_MODE,
            ),
            call(
                user=user,
                runs=[enrollments[0].run],
                change_status=ENROLL_CHANGE_STATUS_DEFERRED,
                keep_failed_enrollments=True,
                mode=EDX_ENROLLMENT_AUDIT_MODE,
            ),
        ]
    )

    defer_enrollment(
        user,
        enrollments[1].run.courseware_id,
        enrollments[2].run.courseware_id,
        force=True,
    )
    assert patched_create_enrollments.call_count == 4


@pytest.mark.parametrize(
    "mocked_api_response, expect_success",  # noqa: PT006
    [
        [  # noqa: PT007
            CourseDetail(
                {
                    "id": "course-v1:edX+DemoX+2020_T1",
                    "start": "2019-01-01T00:00:00Z",
                    "end": "2020-02-01T00:00:00Z",
                    "enrollment_start": "2019-01-01T00:00:00Z",
                    "enrollment_end": "2020-02-01T00:00:00Z",
                    "name": "Demonstration Course",
                    "pacing": "self",
                }
            ),
            True,
        ],
        [  # noqa: PT007
            CourseDetail(
                {
                    "id": "course-v1:edX+DemoX+2020_T1",
                    "start": "2019-01-01T00:00:00Z",
                    "end": "2020-02-01T00:00:00Z",
                    "enrollment_start": "2019-01-01T00:00:00Z",
                    "enrollment_end": "2020-02-01T00:00:00Z",
                    "name": "Demonstration Course",
                    "pacing": "instructor",
                }
            ),
            True,
        ],
        [  # noqa: PT007
            CourseDetail(
                {
                    "id": "course-v1:edX+DemoX+2020_T1",
                    "start": "2021-01-01T00:00:00Z",
                    "end": "2020-02-01T00:00:00Z",
                    "enrollment_start": None,
                    "enrollment_end": None,
                    "name": None,
                }
            ),
            False,
        ],
        [HTTPError(response=Mock(status_code=404)), False],  # noqa: PT007
        [HTTPError(response=Mock(status_code=400)), False],  # noqa: PT007
        [ConnectionError(), False],  # noqa: PT007
    ],
)
def test_sync_course_runs(settings, mocker, mocked_api_response, expect_success):
    """
    Test that sync_course_runs fetches data from edX API. Should fail on API responding with
    an error, as well as trying to set the course run title to None
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
    mocker.patch.object(CourseDetails, "get_detail", side_effect=[mocked_api_response])
    course_run = CourseRunFactory.create()

    success_count, failure_count = sync_course_runs([course_run])

    if expect_success:
        course_run.refresh_from_db()
        assert success_count == 1
        assert failure_count == 0
        assert course_run.title == mocked_api_response.name
        assert course_run.start_date == mocked_api_response.start
        assert course_run.end_date == mocked_api_response.end
        assert course_run.enrollment_start == mocked_api_response.enrollment_start
        assert course_run.enrollment_end == mocked_api_response.enrollment_end
        assert course_run.is_self_paced == mocked_api_response.is_self_paced()
    else:
        assert success_count == 0
        assert failure_count == 1


@pytest.mark.parametrize(
    "mocked_api_response, expect_success",  # noqa: PT006
    [
        [  # noqa: PT007
            [
                CourseMode(
                    {
                        "expiration_datetime": "2019-01-01T00:00:00Z",
                        "mode_slug": "verified",
                    }
                )
            ],
            True,
        ],
        [  # noqa: PT007
            [CourseMode({"expiration_datetime": "", "mode_slug": "audit"})],
            True,
        ],
        [  # noqa: PT007
            [
                CourseMode({"expiration_datetime": "", "mode_slug": "audit"}),
                CourseMode(
                    {
                        "expiration_datetime": "2019-01-01T00:00:00Z",
                        "mode_slug": "verified",
                    }
                ),
            ],
            True,
        ],
        [HTTPError(response=Mock(status_code=404)), False],  # noqa: PT007
        [HTTPError(response=Mock(status_code=400)), False],  # noqa: PT007
        [ConnectionError(), False],  # noqa: PT007
    ],
)
def test_sync_course_mode(settings, mocker, mocked_api_response, expect_success):
    """
    Test that sync_course_mode fetches data from edX API. Should fail on API
    responding with an error.
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"  # noqa: S105
    mocker.patch.object(CourseModes, "get_mode", side_effect=[mocked_api_response])
    course_run = CourseRunFactory.create()

    success_count, failure_count = sync_course_mode([course_run])

    if expect_success:
        if all(course_mode.mode_slug == "audit" for course_mode in mocked_api_response):
            course_run.refresh_from_db()
            assert success_count == 0
            assert failure_count == 0
        else:
            course_run.refresh_from_db()
            assert success_count == 1
            assert failure_count == 0
            assert course_run.upgrade_deadline == next(
                course_mode.expiration_datetime
                for course_mode in mocked_api_response
                if course_mode.mode_slug == "verified"
            )
    else:
        assert success_count == 0
        assert failure_count == 1


@pytest.mark.parametrize(
    "grade, passed, paid, exp_certificate, exp_created, exp_deleted",  # noqa: PT006
    [
        [0.25, True, True, True, True, False],  # noqa: PT007
        [0.25, True, False, False, False, False],  # noqa: PT007
        [0.0, True, True, False, False, False],  # noqa: PT007
        [1.0, False, True, False, False, False],  # noqa: PT007
    ],
)
def test_course_run_certificate(  # noqa: PLR0913
    user,
    passed_grade_with_enrollment,
    grade,
    paid,
    passed,
    exp_certificate,
    exp_created,
    exp_deleted,
    mocker,
):
    """
    Test that the certificate is generated correctly
    """
    patched_sync_hubspot_user = mocker.patch(
        "hubspot_sync.task_helpers.sync_hubspot_user",
    )
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    passed_grade_with_enrollment.grade = grade
    passed_grade_with_enrollment.passed = passed
    if not paid:
        CourseRunEnrollment.objects.filter(
            user=passed_grade_with_enrollment.user,
            run=passed_grade_with_enrollment.course_run,
        ).update(enrollment_mode=EDX_DEFAULT_ENROLLMENT_MODE)

    certificate, created, deleted = process_course_run_grade_certificate(
        passed_grade_with_enrollment
    )
    if created:
        patched_sync_hubspot_user.assert_called_once_with(user)
    assert bool(certificate) is exp_certificate
    assert created is exp_created
    assert deleted is exp_deleted


def test_course_run_certificate_idempotent(passed_grade_with_enrollment, mocker, user):
    """
    Test that the certificate generation is idempotent
    """
    patched_sync_hubspot_user = mocker.patch(
        "hubspot_sync.task_helpers.sync_hubspot_user",
    )
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    # Certificate is created the first time
    certificate, created, deleted = process_course_run_grade_certificate(
        passed_grade_with_enrollment
    )
    assert certificate
    assert created
    assert not deleted

    patched_sync_hubspot_user.assert_called_once_with(user)

    # Existing certificate is simply returned without any create/delete
    certificate, created, deleted = process_course_run_grade_certificate(
        passed_grade_with_enrollment
    )
    assert certificate
    assert not created
    assert not deleted


def test_course_run_certificate_not_passing(passed_grade_with_enrollment, mocker):
    """
    Test that the certificate is not generated if the grade is set to not passed
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    # Initially the certificate is created
    certificate, created, deleted = process_course_run_grade_certificate(
        passed_grade_with_enrollment
    )
    assert certificate
    assert created
    assert not deleted

    # Now that the grade indicates score 0.0, certificate should be deleted
    passed_grade_with_enrollment.grade = 0.0
    certificate, created, deleted = process_course_run_grade_certificate(
        passed_grade_with_enrollment
    )
    assert not certificate
    assert not created
    assert deleted


def test_generate_course_certificates_no_valid_course_run(settings, courses_api_logs):
    """Test that a proper message is logged when there is no valid course run to generate certificates"""
    generate_course_run_certificates()
    assert (
        "No course runs matched the certificates generation criteria"
        in courses_api_logs.info.call_args[0][0]
    )

    # Create a batch of Course Runs that doesn't match certificate generation filter
    CourseRunFactory.create_batch(
        5,
        is_self_paced=False,
        certificate_available_date=now_in_utc()
        - timedelta(days=settings.CERTIFICATE_CREATION_WINDOW_IN_DAYS + 1),
    )
    generate_course_run_certificates()
    assert (
        "No course runs matched the certificates generation criteria"
        in courses_api_logs.info.call_args[0][0]
    )


def test_generate_course_certificates_self_paced_course(
    mocker, courses_api_logs, passed_grade_with_enrollment
):
    """Test that certificates are generated for self paced course runs independent of course run end date"""
    course_run = passed_grade_with_enrollment.course_run
    user = passed_grade_with_enrollment.user
    course_run.is_self_paced = True
    course_run.save()
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    mocker.patch(
        "courses.api.ensure_course_run_grade",
        return_value=(passed_grade_with_enrollment, True, False),
    )
    mocker.patch(
        "courses.api.exception_logging_generator",
        return_value=[(passed_grade_with_enrollment, user)],
    )
    generate_course_run_certificates()
    assert (
        f"Finished processing course run {course_run}: created grades for {1} users, updated grades for {0} users, generated certificates for {1} users"
        in courses_api_logs.info.call_args[0][0]
    )


@pytest.mark.parametrize(
    "self_paced, end_date",  # noqa: PT006
    [
        (True, now_in_utc() + timedelta(hours=2)),
        (False, now_in_utc()),
        (False, None),
    ],
)
def test_course_certificates_with_course_end_date_self_paced_combination(  # noqa: PLR0913
    mocker,
    settings,
    courses_api_logs,
    passed_grade_with_enrollment,
    self_paced,
    end_date,
):
    """Test that correct certificates are created when there are course runs with end_date and self_paced combination"""
    course_run = passed_grade_with_enrollment.course_run
    course_run.is_self_paced = self_paced
    course_run.certificate_available_date = end_date
    course_run.save()

    user = passed_grade_with_enrollment.user

    mocker.patch(
        "hubspot_sync.task_helpers.sync_hubspot_user",
    )
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    mocker.patch(
        "courses.api.exception_logging_generator",
        return_value=[(passed_grade_with_enrollment, user)],
    )

    mocker.patch(
        "courses.api.ensure_course_run_grade",
        return_value=(passed_grade_with_enrollment, True, False),
    )

    generate_course_run_certificates()
    assert (
        f"Finished processing course run {course_run}: created grades for {1} users, updated grades for {0} users, generated certificates for {1 if end_date else 0} users"
        in courses_api_logs.info.call_args[0][0]
    )


def test_generate_course_certificates_with_course_end_date(
    mocker, courses_api_logs, passed_grade_with_enrollment, settings
):
    """Test that certificates are generated for passed grades when there are valid course runs for certificates"""
    course_run = passed_grade_with_enrollment.course_run
    course_run.certificate_available_date = now_in_utc()
    course_run.save()

    user = passed_grade_with_enrollment.user
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    mocker.patch(
        "courses.api.ensure_course_run_grade",
        return_value=(passed_grade_with_enrollment, True, False),
    )
    mocker.patch(
        "courses.api.exception_logging_generator",
        return_value=[(passed_grade_with_enrollment, user)],
    )
    generate_course_run_certificates()
    assert (
        f"Finished processing course run {course_run}: created grades for {1} users, updated grades for {0} users, generated certificates for {1} users"
        in courses_api_logs.info.call_args[0][0]
    )


def test_course_run_certificates_access(mocker):
    """Tests that the revoke and unrevoke for a course run certificates sets the states properly"""
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    test_certificate = CourseRunCertificateFactory.create(is_revoked=False)

    # Revoke a certificate
    manage_course_run_certificate_access(
        user=test_certificate.user,
        courseware_id=test_certificate.course_run.courseware_id,
        revoke_state=True,
    )

    test_certificate.refresh_from_db()
    assert test_certificate.is_revoked is True

    # Unrevoke a certificate
    manage_course_run_certificate_access(
        user=test_certificate.user,
        courseware_id=test_certificate.course_run.courseware_id,
        revoke_state=False,
    )
    test_certificate.refresh_from_db()
    assert test_certificate.is_revoked is False


@pytest.mark.parametrize(
    "grade, letter_grade, should_force_pass, is_passed",  # noqa: PT006
    [
        (0.0, "F", True, False),
        (0.1, "F", True, True),
        (0.5, "C", False, False),
        (0.5, "C", True, True),
    ],
)
def test_override_user_grade(grade, letter_grade, should_force_pass, is_passed):
    """Test the override grade overrides the user grade properly"""
    test_grade = CourseRunGradeFactory.create()
    override_user_grade(
        user=test_grade.user,
        override_grade=grade,
        letter_grade=letter_grade,
        courseware_id=test_grade.course_run.courseware_id,
        should_force_pass=should_force_pass,
    )
    test_grade.refresh_from_db()
    assert test_grade.grade == grade
    assert test_grade.passed is is_passed
    assert test_grade.letter_grade is letter_grade
    assert test_grade.set_by_admin is True


def test_create_run_enrollments_upgrade_edx_request_failure(mocker, user):
    """
    create_run_enrollments should call the edX API to create/update enrollments, and set the enrollment mode properly
    on mitxonline.  If the edx API call to update the course_mode from audit -> verified fails, then edx_request_success
    should return as False and the course_run_enrollment's edx_enrolled value should be set to False.
    In addition, tests to make sure there's a ProgramEnrollment for the course.
    """
    test_course_run = CourseRunFactory.create()
    patched_edx_enroll = mocker.patch("courses.api.enroll_in_edx_course_runs")
    patched_send_enrollment_email = mocker.patch(
        "courses.api.mail_api.send_course_run_enrollment_email"
    )
    mocker.patch("courses.tasks.subscribe_edx_course_emails.delay")

    successful_enrollments, edx_request_success = create_run_enrollments(
        user,
        runs=[test_course_run],
        keep_failed_enrollments=True,
        mode=EDX_ENROLLMENT_AUDIT_MODE,
    )
    patched_edx_enroll.assert_called_once_with(
        user,
        [test_course_run],
        mode=EDX_ENROLLMENT_AUDIT_MODE,
    )

    patched_send_enrollment_email.assert_called_once()
    assert edx_request_success is True
    assert successful_enrollments[0].enrollment_mode == EDX_ENROLLMENT_AUDIT_MODE

    patched_edx_enroll = mocker.patch(
        "courses.api.enroll_in_edx_course_runs",
        side_effect=UnknownEdxApiEnrollException(user, test_course_run, Exception()),
    )
    patched_log_exception = mocker.patch("courses.api.log.exception")  # noqa: F841
    successful_enrollments, edx_request_success = create_run_enrollments(
        user,
        runs=[test_course_run],
        keep_failed_enrollments=True,
        mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )

    patched_edx_enroll.assert_called_once_with(
        user,
        [test_course_run],
        mode=EDX_ENROLLMENT_VERIFIED_MODE,
    )

    assert edx_request_success is False
    assert successful_enrollments[0].enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE
    assert successful_enrollments[0].edx_enrolled == False  # noqa: E712


def test_generate_program_certificate_failure_missing_certificates(
    user,
    program_with_requirements,  # noqa: F811
):
    """
    Test that generate_program_certificate return (None, False) and not create program certificate
    if there is not any course_run certificate for the given course.
    """
    course = CourseFactory.create()
    CourseRunFactory.create_batch(3, course=course)
    ProgramRequirementFactory.add_root(program_with_requirements.program)
    program_with_requirements.program.add_requirement(course)

    result = generate_program_certificate(
        user=user, program=program_with_requirements.program
    )
    assert result == (None, False)
    assert len(ProgramCertificate.objects.all()) == 0


def test_generate_program_certificate_failure_not_all_passed(
    user,
    program_with_requirements,  # noqa: F811
    mocker,
):
    """
    Test that generate_program_certificate return (None, False) and not create program certificate
    if there is not any course_run certificate for the given course.
    """
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    courses = CourseFactory.create_batch(3)
    course_runs = CourseRunFactory.create_batch(3, course=factory.Iterator(courses))
    CourseRunCertificateFactory.create_batch(
        2, user=user, course_run=factory.Iterator(course_runs)
    )
    program = program_with_requirements.program
    program.add_requirement(courses[0])
    program.add_requirement(courses[1])
    program.add_requirement(courses[2])

    result = generate_program_certificate(user=user, program=program)
    assert result == (None, False)
    assert len(ProgramCertificate.objects.all()) == 0


def test_generate_program_certificate_success_single_requirement_course(user, mocker):
    """
    Test that generate_program_certificate generates a program certificate for a Program with a single required Course.
    """
    patched_sync_hubspot_user = mocker.patch(
        "hubspot_sync.task_helpers.sync_hubspot_user",
    )
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    course = CourseFactory.create()
    program = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    program.add_requirement(course)
    course_run = CourseRunFactory.create(course=course)
    CourseRunGradeFactory.create(course_run=course_run, user=user, passed=True, grade=1)

    CourseRunCertificateFactory.create(user=user, course_run=course_run)

    certificate, created = generate_program_certificate(user=user, program=program)
    assert created is True
    assert isinstance(certificate, ProgramCertificate)
    assert len(ProgramCertificate.objects.all()) == 1
    patched_sync_hubspot_user.assert_called_once_with(user)


def test_generate_program_certificate_success_multiple_required_courses(user, mocker):
    """
    Test that generate_program_certificate generate a program certificate
    """
    patched_sync_hubspot_user = mocker.patch(
        "hubspot_sync.task_helpers.sync_hubspot_user",
    )
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    courses = CourseFactory.create_batch(3)
    program = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    for course in courses:
        program.add_requirement(course)
    course_runs = CourseRunFactory.create_batch(3, course=factory.Iterator(courses))
    CourseRunCertificateFactory.create_batch(
        3, user=user, course_run=factory.Iterator(course_runs)
    )

    certificate, created = generate_program_certificate(user=user, program=program)
    assert created is True
    assert isinstance(certificate, ProgramCertificate)
    assert len(ProgramCertificate.objects.all()) == 1
    patched_sync_hubspot_user.assert_called_once_with(user)


def test_generate_program_certificate_success_minimum_electives_not_met(user, mocker):
    """
    Test that generate_program_certificate does not generate a program certificate if minimum electives have not been met.
    """
    courses = CourseFactory.create_batch(3)
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )

    # Create Program with 2 minimum elective courses.
    program = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )
    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=2,
        title="Elective Courses",
    )
    required_course1 = courses[0]
    elective_course1 = courses[1]
    elective_course2 = courses[2]
    program.add_requirement(required_course1)
    program.add_elective(elective_course1)
    program.add_elective(elective_course2)

    required_course1_course_run = CourseRunFactory.create(course=required_course1)
    elective_course1_course_run = CourseRunFactory.create(course=elective_course1)
    elective_course2_course_run = CourseRunFactory.create(course=elective_course2)  # noqa: F841

    # User has a certificate for required_course1 and elective_course1 only. No certificate for elective_course2.
    CourseRunCertificateFactory.create(
        user=user, course_run=required_course1_course_run
    )
    CourseRunCertificateFactory.create(
        user=user, course_run=elective_course1_course_run
    )

    certificate, created = generate_program_certificate(user=user, program=program)
    assert created is False
    assert len(ProgramCertificate.objects.all()) == 0


def test_force_generate_program_certificate_success(
    user,
    program_with_requirements,  # noqa: F811
    mocker,
):
    """
    Test that force creating a program certificate with generate_program_certificate generates
    a program certificate without matching program certificate requirements.
    """
    patched_sync_hubspot_user = mocker.patch(
        "hubspot_sync.task_helpers.sync_hubspot_user",
    )
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    courses = CourseFactory.create_batch(3)
    course_runs = CourseRunFactory.create_batch(3, course=factory.Iterator(courses))
    CourseRunCertificateFactory.create_batch(
        2, user=user, course_run=factory.Iterator(course_runs)
    )
    program = program_with_requirements.program
    program.add_requirement(courses[0])
    program.add_requirement(courses[1])
    program.add_requirement(courses[2])

    certificate, created = generate_program_certificate(
        user=user, program=program, force_create=True
    )
    assert created is True
    assert isinstance(certificate, ProgramCertificate)
    assert len(ProgramCertificate.objects.all()) == 1
    patched_sync_hubspot_user.assert_called_once_with(user)


def test_generate_program_certificate_already_exist(
    user,
    program_with_empty_requirements,  # noqa: F811
):
    """
    Test that generate_program_certificate return (None, False) and not create program certificate
    if program certificate already exist.
    """
    program_certificate = ProgramCertificateFactory.create(
        program=program_with_empty_requirements, user=user
    )
    result = generate_program_certificate(
        user=user, program=program_with_empty_requirements
    )
    assert result == (program_certificate, False)
    assert len(ProgramCertificate.objects.all()) == 1


def test_program_certificates_access():
    """Tests that the revoke and unrevoke for a program certificates sets the states properly"""
    test_certificate = ProgramCertificateFactory.create(is_revoked=False)

    # Revoke a program certificate
    manage_program_certificate_access(
        user=test_certificate.user,
        program=test_certificate.program,
        revoke_state=True,
    )

    test_certificate.refresh_from_db()
    assert test_certificate.is_revoked is True

    # Unrevoke a program certificate
    manage_program_certificate_access(
        user=test_certificate.user,
        program=test_certificate.program,
        revoke_state=False,
    )
    test_certificate.refresh_from_db()
    assert test_certificate.is_revoked is False


def test_generate_program_certificate_failure_not_all_passed_nested_elective_stipulation(
    user,
    mocker,
):
    """
    Test that generate_program_certificate returns (None, False) and does not create a program certificate
    if the learner has not met the elective requirements due to a nested operator.
    """
    courses = CourseFactory.create_batch(3)
    course_runs = CourseRunFactory.create_batch(3, course=factory.Iterator(courses))
    mocker.patch(
        "hubspot_sync.management.commands.configure_hubspot_properties._upsert_custom_properties",
    )
    # Create Program
    program = ProgramFactory.create()
    ProgramRequirementFactory.add_root(program)
    root_node = program.requirements_root

    root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.ALL_OF,
        title="Required Courses",
    )

    # Add main electives requirement.
    elective_courses_node = root_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=2,
        title="Elective Courses",
    )

    # Add stipulation to electives.
    # Only 1 course belonging to this subset is counted towards the Program's elective requirement.
    mut_exclusive_courses_node = elective_courses_node.add_child(
        node_type=ProgramRequirementNodeType.OPERATOR,
        operator=ProgramRequirement.Operator.MIN_NUMBER_OF,
        operator_value=1,
    )
    # Add 2 courses within the stipulation.
    mut_exclusive_courses_node.add_child(
        node_type=ProgramRequirementNodeType.COURSE, course=courses[1]
    )
    mut_exclusive_courses_node.add_child(
        node_type=ProgramRequirementNodeType.COURSE, course=courses[2]
    )

    # Create certificates for both courses within the stipulation.
    CourseRunCertificateFactory.create(user=user, course_run=course_runs[1])
    CourseRunCertificateFactory.create(user=user, course_run=course_runs[2])

    # Only one of the two certificates for courses in the elective stipulation should contribute towards
    # the Program's elective requirements.
    result = generate_program_certificate(user=user, program=program)
    assert result == (None, False)
    assert len(ProgramCertificate.objects.all()) == 0


def test_program_enrollment_unenrollment_re_enrollment(
    mocker,
    user,
    program_with_empty_requirements,  # noqa: F811
):
    """
    create_run_enrollments should always enroll a learner into a program even
    if the learner has previously unenrolled from the program.
    """

    # Create a program_enrollment that mocks what exists after a learner unenrolls from
    # a program.
    ProgramEnrollmentFactory(
        user=user,
        program=program_with_empty_requirements,
        change_status=ENROLL_CHANGE_STATUS_UNENROLLED,
    )
    course_run = CourseRunFactory.create()
    program_with_empty_requirements.add_requirement(course_run.course)
    mocker.patch("courses.api.enroll_in_edx_course_runs")
    mocker.patch("courses.api.mail_api.send_course_run_enrollment_email")
    mocker.patch("courses.tasks.subscribe_edx_course_emails.delay")

    create_run_enrollments(user, runs=[course_run], mode=EDX_ENROLLMENT_VERIFIED_MODE)
    assert ProgramEnrollment.objects.filter(
        user=user, program=program_with_empty_requirements, change_status=None
    ).exists()
