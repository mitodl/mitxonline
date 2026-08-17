"""Tests for command utils"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from mitol.common.utils.datetime import now_in_utc

from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
)
from courses.management.utils import (
    EnrollmentChangeCommand,
    bulk_enroll_learners,
    enroll_learner_in_run,
)
from main.test_utils import MockHttpError
from openedx.exceptions import EdxApiEnrollErrorException, UnknownEdxApiEnrollException
from users.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize("keep_failed_enrollments", [True, False])
@pytest.mark.parametrize(
    "exception_cls,inner_exception",  # noqa: PT006
    [
        [EdxApiEnrollErrorException, MockHttpError()],  # noqa: PT007
        [UnknownEdxApiEnrollException, Exception()],  # noqa: PT007
    ],
)
def test_create_run_enrollment_edx_failure(
    mocker, keep_failed_enrollments, exception_cls, inner_exception
):
    """Test that create_run_enrollment behaves as expected when the enrollment fails in edX"""
    now = now_in_utc()
    user = UserFactory()
    existing_enrollment = CourseRunEnrollmentFactory(user=user)
    non_program_run = CourseRunFactory.create(start_date=(now + timedelta(days=1)))
    expected_enrollment = CourseRunEnrollmentFactory(user=user, run=non_program_run)

    patched_edx_enroll = mocker.patch(
        "courses.management.utils.enroll_in_edx_course_runs",
        side_effect=exception_cls(user, non_program_run, inner_exception),
    )

    new_enrollment = EnrollmentChangeCommand().create_run_enrollment(
        existing_enrollment=existing_enrollment,
        to_user=user,
        to_run=non_program_run,
        keep_failed_enrollments=keep_failed_enrollments,
    )

    patched_edx_enroll.assert_called_once_with(user, [non_program_run])

    if keep_failed_enrollments:
        assert new_enrollment == expected_enrollment
    else:
        assert new_enrollment is None


@pytest.mark.django_db()
class TestEnrollLearnerInRun:
    """Tests for the enroll_learner_in_run utility function"""

    def test_creates_openedx_user_if_missing(self, mocker):
        """Should create the learner's edX account first if they don't have one"""
        user = UserFactory.create(no_openedx_user=True)
        run = CourseRunFactory.create()
        mock_create_user = mocker.patch("courses.management.utils.create_user")
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([enrollment], True),
        )

        enroll_learner_in_run(user, run)

        mock_create_user.assert_called_once_with(user)

    def test_skips_openedx_user_creation_if_exists(self, mocker):
        """Should not try to create an edX account if the learner already has one"""
        user = UserFactory.create()  # has a synced openedx_user by default
        run = CourseRunFactory.create()
        mock_create_user = mocker.patch("courses.management.utils.create_user")
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([enrollment], True),
        )

        enroll_learner_in_run(user, run)

        mock_create_user.assert_not_called()

    def test_successful_enrollment(self, mocker):
        """Should return the created enrollment and a success message"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch("courses.management.utils.create_user")
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([enrollment], True),
        )

        result, message = enroll_learner_in_run(user, run)

        assert result == enrollment
        assert user.email in message
        assert run.courseware_id in message

    def test_edx_failure_still_reports_success_with_note(self, mocker):
        """Should still return the enrollment but note the edX failure"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch("courses.management.utils.create_user")
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([enrollment], False),
        )

        result, message = enroll_learner_in_run(user, run)

        assert result == enrollment
        assert "edX enrollment failed" in message

    def test_failed_enrollment(self, mocker):
        """Should return None and a failure message when no enrollment is created"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch("courses.management.utils.create_user")
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([], False),
        )

        result, message = enroll_learner_in_run(user, run)

        assert result is None
        assert "Failed to enroll" in message

    def test_openedx_connection_failure_does_not_raise(self, mocker):
        """
        Should catch (not propagate) an exception raised by create_user, e.g. when
        edX is unreachable. create_user re-raises unless IGNORE_EDX_FAILURES is set,
        so this must be caught here or it kills the entire bulk_enroll_learners loop.
        """
        user = UserFactory.create(no_openedx_user=True)
        run = CourseRunFactory.create()
        mocker.patch(
            "courses.management.utils.create_user",
            side_effect=ConnectionError("edX is unreachable"),
        )
        mock_create_run_enrollments = mocker.patch(
            "courses.management.utils.create_run_enrollments"
        )

        result, message = enroll_learner_in_run(user, run)

        assert result is None
        assert "Failed to enroll" in message
        assert "edX is unreachable" in message
        mock_create_run_enrollments.assert_not_called()

    def test_create_run_enrollments_failure_does_not_raise(self, mocker):
        """Should catch (not propagate) an unexpected exception from create_run_enrollments"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch("courses.management.utils.create_user")
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            side_effect=ConnectionError("edX is unreachable"),
        )

        result, message = enroll_learner_in_run(user, run)

        assert result is None
        assert "Failed to enroll" in message

    def test_mode_passed_through(self, mocker):
        """Should pass the mode and keep_failed_enrollments through to create_run_enrollments"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch("courses.management.utils.create_user")
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mock_create_run_enrollments = mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([enrollment], True),
        )

        enroll_learner_in_run(user, run, mode="verified", keep_failed_enrollments=True)

        mock_create_run_enrollments.assert_called_once_with(
            user, [run], keep_failed_enrollments=True, mode="verified"
        )


@pytest.mark.django_db()
class TestBulkEnrollLearnersUtil:
    """Tests for the bulk_enroll_learners utility function"""

    def test_successful_enrollment(self, mocker):
        """Should enroll a valid user/run pair successfully"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mocker.patch(
            "courses.management.utils.enroll_learner_in_run",
            return_value=(enrollment, f"Enrolled {user.email} in {run.courseware_id}"),
        )

        result = bulk_enroll_learners([(user.email, run.courseware_id)])

        assert result["succeeded"] == 1
        assert result["failed"] == 0
        assert result["skipped"] == 0

    def test_user_not_found(self):
        """Should skip when user doesn't exist"""
        run = CourseRunFactory.create()
        result = bulk_enroll_learners([("nonexistent@example.com", run.courseware_id)])

        assert result["skipped"] == 1
        assert result["succeeded"] == 0

    def test_course_run_not_found(self):
        """Should skip when course run doesn't exist"""
        user = UserFactory.create()
        result = bulk_enroll_learners([(user.email, "course-v1:fake+fake+fake")])

        assert result["skipped"] == 1
        assert result["succeeded"] == 0

    def test_enrollment_failure(self, mocker):
        """Should count as failed when enroll_learner_in_run returns None"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch(
            "courses.management.utils.enroll_learner_in_run",
            return_value=(None, "Failed to enroll"),
        )

        result = bulk_enroll_learners([(user.email, run.courseware_id)])

        assert result["failed"] == 1
        assert result["succeeded"] == 0

    def test_mode_and_keep_failed_passed(self, mocker):
        """Should pass mode and keep_failed_enrollments to enroll_learner_in_run"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        enrollment = CourseRunEnrollmentFactory.build(user=user, run=run)
        mock_enroll = mocker.patch(
            "courses.management.utils.enroll_learner_in_run",
            return_value=(enrollment, "Enrolled"),
        )

        bulk_enroll_learners(
            [(user.email, run.courseware_id)],
            mode="verified",
            keep_failed_enrollments=True,
        )

        mock_enroll.assert_called_once_with(
            user, run, mode="verified", keep_failed_enrollments=True
        )

    def test_one_bad_row_does_not_abort_the_batch(self, mocker):
        """
        A row whose edX call raises (e.g. edX unreachable) should be recorded as
        failed, not propagate and abort processing of the remaining entries.
        Regression test: enroll_learner_in_run previously had no try/except
        around create_user(), so this would raise straight out of the loop.
        """
        good_user = UserFactory.create()
        bad_user = UserFactory.create(no_openedx_user=True)
        run = CourseRunFactory.create()
        enrollment = CourseRunEnrollmentFactory.build(user=good_user, run=run)

        def create_user_side_effect(user):
            if user == bad_user:
                msg = "edX is unreachable"
                raise ConnectionError(msg)

        mocker.patch(
            "courses.management.utils.create_user",
            side_effect=create_user_side_effect,
        )
        mocker.patch(
            "courses.management.utils.create_run_enrollments",
            return_value=([enrollment], True),
        )

        result = bulk_enroll_learners(
            [
                (bad_user.email, run.courseware_id),
                (good_user.email, run.courseware_id),
            ]
        )

        assert result["failed"] == 1
        assert result["succeeded"] == 1

    def test_course_run_cached_across_entries(self, mocker):
        """Should only query for a given courseware_id once across multiple entries"""
        user1 = UserFactory.create()
        user2 = UserFactory.create()
        run = CourseRunFactory.create()
        mocker.patch(
            "courses.management.utils.enroll_learner_in_run",
            return_value=(
                CourseRunEnrollmentFactory.build(user=user1, run=run),
                "Enrolled",
            ),
        )
        mock_filter = mocker.patch(
            "courses.management.utils.CourseRun.objects.filter",
            wraps=None,
        )
        mock_filter.return_value.first.return_value = run

        bulk_enroll_learners(
            [
                (user1.email, run.courseware_id),
                (user2.email, run.courseware_id),
            ]
        )

        mock_filter.assert_called_once_with(courseware_id=run.courseware_id)
