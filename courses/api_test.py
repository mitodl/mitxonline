"""Courses API tests"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import factory
import pytest
from django.core.exceptions import ValidationError
from edx_api.course_detail import CourseDetail, CourseDetails
from mitol.common.utils.datetime import now_in_utc
from requests import ConnectionError as RequestsConnectionError
from requests import HTTPError

from courses.api import (
    get_user_relevant_course_run,
    create_program_enrollments,
    create_run_enrollments,
    deactivate_program_enrollment,
    deactivate_run_enrollment,
    defer_enrollment,
    get_user_enrollments,
    sync_course_runs,
)
from courses.constants import (
    ENROLL_CHANGE_STATUS_DEFERRED,
    ENROLL_CHANGE_STATUS_REFUNDED,
)
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramEnrollmentFactory,
    ProgramFactory,
)

# pylint: disable=redefined-outer-name
from courses.models import CourseRunEnrollment, ProgramEnrollment
from main.test_utils import MockHttpError
from openedx.constants import EDX_DEFAULT_ENROLLMENT_MODE
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


@pytest.mark.parametrize("is_enrolled", [True, False])
def test_get_user_relevant_course_run(user, dates, is_enrolled):
    """
    get_user_relevant_course_run should return an enrolled run if the end date isn't in the past, or the soonest course
    run that does not have a past enrollment end date.
    """
    course = CourseFactory.create()
    # One run in the near future, one run in progress with an expired enrollment period, and one run in the far future.
    course_runs = CourseRunFactory.create_batch(
        3,
        course=course,
        start_date=factory.Iterator(
            [dates.future_10_days, dates.past_10_days, dates.future_30_days]
        ),
        end_date=factory.Iterator([None, dates.future_10_days, dates.future_60_days]),
        enrollment_start=factory.Iterator(
            [dates.future_10_days, dates.past_60_days, dates.future_30_days]
        ),
        enrollment_end=factory.Iterator(
            [None, dates.past_30_days, dates.future_60_days]
        ),
    )
    if is_enrolled:
        # Enroll in the in-progress course run
        CourseRunEnrollmentFactory.create(
            run=course_runs[1], user=user, edx_enrolled=True, active=True
        )
    returned_run = get_user_relevant_course_run(course=course, user=user)
    assert returned_run == (course_runs[1] if is_enrolled else course_runs[0])


def test_get_user_relevant_course_run_invalid_dates(user, dates):
    """
    get_user_relevant_course_run should ignore course runs with any of the following properties:
    1) No start date or enrollment start date
    2) An end date in the past

    """
    course = CourseFactory.create()
    CourseRunFactory.create_batch(
        3,
        course=course,
        start_date=factory.Iterator([None, dates.future_10_days, dates.past_30_days]),
        end_date=factory.Iterator([None, dates.future_60_days, dates.past_10_days]),
        enrollment_start=factory.Iterator(
            [dates.future_10_days, None, dates.past_30_days]
        ),
        enrollment_end=factory.Iterator(
            [dates.future_60_days, None, dates.past_10_days]
        ),
    )
    returned_run = get_user_relevant_course_run(course=course, user=user)
    assert returned_run is None


def test_get_user_relevant_course_run_ignore_enrolled(user, dates):
    """
    get_user_relevant_course_run return a future course run if an enrolled run's end date is in the past, or if an
    enrollment for an open course is not flagged as edX-enrolled
    """
    course = CourseFactory.create()
    course_runs = CourseRunFactory.create_batch(
        3,
        course=course,
        start_date=factory.Iterator(
            [dates.past_30_days, dates.now, dates.future_10_days]
        ),
        end_date=factory.Iterator(
            [dates.past_10_days, dates.future_10_days, dates.future_30_days]
        ),
        enrollment_start=factory.Iterator(
            [dates.past_30_days, dates.past_30_days, dates.future_10_days]
        ),
        enrollment_end=factory.Iterator(
            [dates.past_10_days, dates.past_10_days, dates.future_30_days]
        ),
    )
    # Enroll in a past course run
    CourseRunEnrollmentFactory.create(
        run=course_runs[0], user=user, edx_enrolled=True, active=True
    )
    # Enroll in a currently-open course run with a closed enrollment period, but set to inactive
    CourseRunEnrollmentFactory.create(
        run=course_runs[1], user=user, edx_enrolled=False, active=True
    )
    returned_run = get_user_relevant_course_run(course=course, user=user)
    # Returned course run should be the one with the unexpired enrollment period
    assert returned_run == course_runs[2]


def test_get_user_enrollments(user):
    """Test that get_user_enrollments returns an object with a user's program and course enrollments"""
    past_date = now_in_utc() - timedelta(days=1)
    past_start_dates = [
        now_in_utc() - timedelta(days=2),
        now_in_utc() - timedelta(days=3),
        now_in_utc() - timedelta(days=4),
    ]
    program = ProgramFactory.create()
    past_program = ProgramFactory.create()

    program_course_runs = CourseRunFactory.create_batch(3, course__program=program)
    past_program_course_runs = CourseRunFactory.create_batch(
        3,
        start_date=factory.Iterator(past_start_dates),
        end_date=past_date,
        course__program=past_program,
    )
    non_program_course_runs = CourseRunFactory.create_batch(2, course__program=None)
    past_non_program_course_runs = CourseRunFactory.create_batch(
        2,
        start_date=factory.Iterator(past_start_dates),
        end_date=past_date,
        course__program=None,
    )
    all_course_runs = (
        program_course_runs
        + past_program_course_runs
        + non_program_course_runs
        + past_non_program_course_runs
    )
    course_run_enrollments = CourseRunEnrollmentFactory.create_batch(
        len(all_course_runs), run=factory.Iterator(all_course_runs), user=user
    )
    program_enrollment = ProgramEnrollmentFactory.create(program=program, user=user)
    past_program_enrollment = ProgramEnrollmentFactory.create(
        program=past_program, user=user
    )
    # Add a non-active enrollment so we can confirm that it isn't returned
    CourseRunEnrollmentFactory.create(user=user, active=False)

    def key_func(enrollment):
        """Function for sorting runs by start_date"""
        return enrollment.run.start_date

    user_enrollments = get_user_enrollments(user)
    assert list(user_enrollments.programs) == [program_enrollment]
    assert list(user_enrollments.past_programs) == [past_program_enrollment]
    assert list(user_enrollments.program_runs) == sorted(
        [
            run_enrollment
            for run_enrollment in course_run_enrollments
            if run_enrollment.run in program_course_runs + past_program_course_runs
        ],
        key=key_func,
    )
    assert list(user_enrollments.non_program_runs) == sorted(
        [
            run_enrollment
            for run_enrollment in course_run_enrollments
            if run_enrollment.run in non_program_course_runs
        ],
        key=key_func,
    )

    assert list(user_enrollments.past_non_program_runs) == sorted(
        [
            run_enrollment
            for run_enrollment in course_run_enrollments
            if run_enrollment.run in past_non_program_course_runs
        ],
        key=key_func,
    )


def test_create_run_enrollments(mocker, user):
    """
    create_run_enrollments should call the edX API to create enrollments, create or reactivate local
    enrollment records, and notify enrolled users via email
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
    patched_edx_email_subscribe = mocker.patch(
        "courses.api.subscribe_to_edx_course_emails"
    )

    successful_enrollments, edx_request_success = create_run_enrollments(
        user,
        runs,
    )
    patched_edx_enroll.assert_called_once_with(
        user, runs, mode=EDX_DEFAULT_ENROLLMENT_MODE
    )

    assert patched_send_enrollment_email.call_count == num_runs
    assert edx_request_success is True
    assert len(successful_enrollments) == num_runs
    enrollments = CourseRunEnrollment.objects.order_by("run__id").all()
    for (run, enrollment) in zip(runs, enrollments):
        assert enrollment.change_status is None
        assert enrollment.active is True
        assert enrollment.edx_enrolled is True
        assert enrollment.edx_emails_subscription is True
        assert enrollment.run == run
        patched_send_enrollment_email.assert_any_call(enrollment)


@pytest.mark.parametrize(
    "exception_cls", [NoEdxApiAuthError, HTTPError, RequestsConnectionError]
)
def test_create_run_enrollments_api_fail(mocker, user, exception_cls):
    """
    create_run_enrollments should log a message and still create local enrollment records when certain exceptions
    are raised if a flag is set to true
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
        user, [run], mode=EDX_DEFAULT_ENROLLMENT_MODE
    )
    patched_log_exception.assert_called_once()
    patched_send_enrollment_email.assert_not_called()
    assert len(successful_enrollments) == 1
    assert edx_request_success is False


@pytest.mark.parametrize("keep_failed_enrollments", [True, False])
@pytest.mark.parametrize(
    "exception_cls,inner_exception",
    [
        [EdxApiEnrollErrorException, MockHttpError()],
        [UnknownEdxApiEnrollException, Exception()],
    ],
)
def test_create_run_enrollments_enroll_api_fail(
    mocker, user, keep_failed_enrollments, exception_cls, inner_exception
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
        user, runs, mode=EDX_DEFAULT_ENROLLMENT_MODE
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
    enrollment = CourseRunEnrollmentFactory.build(run=runs[1])
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
        user, runs, mode=EDX_DEFAULT_ENROLLMENT_MODE
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
    for (program, enrollment) in zip(programs, enrollments):
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

    @pytest.fixture()
    def patches(self, mocker):  # pylint: disable=missing-docstring
        edx_unenroll = mocker.patch("courses.api.unenroll_edx_course_run")
        send_unenrollment_email = mocker.patch(
            "courses.api.mail_api.send_course_run_unenrollment_email"
        )
        log_exception = mocker.patch("courses.api.log.exception")
        return SimpleNamespace(
            edx_unenroll=edx_unenroll,
            send_unenrollment_email=send_unenrollment_email,
            log_exception=log_exception,
        )

    def test_deactivate_run_enrollment(self, patches):
        """
        deactivate_run_enrollment should attempt to unenroll a user in a course run in edX and set the
        local enrollment record to inactive
        """
        enrollment = CourseRunEnrollmentFactory.create(edx_enrolled=True)

        returned_enrollment = deactivate_run_enrollment(
            enrollment, change_status=ENROLL_CHANGE_STATUS_REFUNDED
        )
        patches.edx_unenroll.assert_called_once_with(enrollment)
        patches.send_unenrollment_email.assert_called_once_with(enrollment)
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
        patches.edx_unenroll.side_effect = Exception

        deactivate_run_enrollment(
            enrollment,
            change_status=ENROLL_CHANGE_STATUS_REFUNDED,
            keep_failed_enrollments=keep_failed_enrollments,
        )
        patches.edx_unenroll.assert_called_once_with(enrollment)
        patches.send_unenrollment_email.assert_not_called()
        patches.log_exception.assert_called_once()
        enrollment.refresh_from_db()
        assert enrollment.active is not keep_failed_enrollments

    def test_deactivate_program_enrollment(self, user, patches):
        """
        deactivate_program_enrollment set the local program enrollment record to inactive as well as all
        associated course run enrollments
        """
        program_enrollment = ProgramEnrollmentFactory.create(user=user)
        course = CourseFactory.create(program=program_enrollment.program)
        course_run_enrollments = CourseRunEnrollmentFactory.create_batch(
            3,
            user=user,
            run__course=course,
            active=True,
        )

        (
            returned_program_enrollment,
            returned_run_enrollments,
        ) = deactivate_program_enrollment(
            program_enrollment, change_status=ENROLL_CHANGE_STATUS_REFUNDED
        )
        program_enrollment.refresh_from_db()
        assert program_enrollment.change_status == ENROLL_CHANGE_STATUS_REFUNDED
        assert program_enrollment.active is False
        assert returned_program_enrollment == program_enrollment
        assert {e.id for e in returned_run_enrollments} == {
            e.id for e in course_run_enrollments
        }
        assert patches.edx_unenroll.call_count == len(course_run_enrollments)
        assert patches.send_unenrollment_email.call_count == len(course_run_enrollments)
        for run_enrollment in course_run_enrollments:
            run_enrollment.refresh_from_db()
            assert run_enrollment.change_status == ENROLL_CHANGE_STATUS_REFUNDED
            assert run_enrollment.active is False
            assert run_enrollment.edx_emails_subscription is False


@pytest.mark.parametrize("keep_failed_enrollments", [True, False])
def test_defer_enrollment(mocker, keep_failed_enrollments):
    """
    defer_enrollment should deactivate a user's existing enrollment and create an enrollment in another
    course run
    """
    course = CourseFactory.create()
    course_runs = CourseRunFactory.create_batch(3, course=course)
    existing_enrollment = CourseRunEnrollmentFactory.create(run=course_runs[0])
    target_run = course_runs[1]
    mock_new_enrollment = mocker.Mock()
    patched_create_enrollments = mocker.patch(
        "courses.api.create_run_enrollments",
        autospec=True,
        return_value=([mock_new_enrollment if keep_failed_enrollments else None], True),
    )
    patched_deactivate_enrollments = mocker.patch(
        "courses.api.deactivate_run_enrollment",
        autospec=True,
        return_value=existing_enrollment if keep_failed_enrollments else None,
    )

    returned_from_enrollment, returned_to_enrollment = defer_enrollment(
        existing_enrollment.user,
        existing_enrollment.run.courseware_id,
        course_runs[1].courseware_id,
        keep_failed_enrollments=keep_failed_enrollments,
    )
    assert returned_from_enrollment == patched_deactivate_enrollments.return_value
    assert returned_to_enrollment == patched_create_enrollments.return_value[0][0]
    patched_create_enrollments.assert_called_once_with(
        existing_enrollment.user,
        [target_run],
        keep_failed_enrollments=keep_failed_enrollments,
    )
    patched_deactivate_enrollments.assert_called_once_with(
        existing_enrollment,
        ENROLL_CHANGE_STATUS_DEFERRED,
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
        "courses.api.create_run_enrollments", return_value=([], False)
    )
    mocker.patch("courses.api.deactivate_run_enrollment", return_value=[])

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
        force=True,
    )
    assert patched_create_enrollments.call_count == 1
    defer_enrollment(
        user,
        enrollments[1].run.courseware_id,
        enrollments[2].run.courseware_id,
        force=True,
    )
    assert patched_create_enrollments.call_count == 2


@pytest.mark.parametrize(
    "mocked_api_response, expect_success",
    [
        [
            CourseDetail(
                {
                    "id": "course-v1:edX+DemoX+2020_T1",
                    "start": "2019-01-01T00:00:00Z",
                    "end": "2020-02-01T00:00:00Z",
                    "enrollment_start": "2019-01-01T00:00:00Z",
                    "enrollment_end": "2020-02-01T00:00:00Z",
                    "name": "Demonstration Course",
                }
            ),
            True,
        ],
        [
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
        [HTTPError(response=Mock(status_code=404)), False],
        [HTTPError(response=Mock(status_code=400)), False],
        [ConnectionError(), False],
    ],
)
def test_sync_course_runs(settings, mocker, mocked_api_response, expect_success):
    """
    Test that sync_course_runs fetches data from edX API. Should fail on API responding with
    an error, as well as trying to set the course run title to None
    """
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "mock_api_token"
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
    else:
        assert success_count == 0
        assert failure_count == 1
