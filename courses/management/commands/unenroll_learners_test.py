"""Tests for unenroll_learners management command"""

import csv
import tempfile
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from users.factories import UserFactory


@pytest.fixture()
def mock_bulk_unenroll(mocker):
    """Mock bulk_unenroll_learners to avoid edX API calls"""
    return mocker.patch(
        "courses.management.commands.unenroll_learners.bulk_unenroll_learners",
        return_value={
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        },
    )


@pytest.mark.django_db()
class TestBulkUnenrollInlineUsers:
    """Tests for --users flag"""

    def test_inline_users_success(self, mock_bulk_unenroll):
        """Unenrolling inline users should call bulk_unenroll_learners with correct entries"""
        mock_bulk_unenroll.return_value = {
            "succeeded": 2,
            "failed": 0,
            "skipped": 0,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Unenrolled: a@b.com from run-1"),
                ("c@d.com", "run-1", "succeeded", "Unenrolled: c@d.com from run-1"),
            ],
        }

        out = StringIO()
        call_command(
            "unenroll_learners",
            users="a@b.com,c@d.com",
            run="run-1",
            stdout=out,
        )

        mock_bulk_unenroll.assert_called_once_with(
            [("a@b.com", "run-1"), ("c@d.com", "run-1")],
            keep_failed_enrollments=False,
        )
        output = out.getvalue()
        assert "2 succeeded" in output
        assert "0 failed" in output

    def test_inline_users_missing_run(self):
        """--users without --run should raise CommandError"""
        with pytest.raises(CommandError, match="--run is required"):
            call_command("unenroll_learners", users="user@example.com")

    def test_inline_users_keep_failed_enrollments(self, mock_bulk_unenroll):
        """--keep-failed-enrollments flag should be passed through"""
        call_command(
            "unenroll_learners",
            users="a@b.com",
            run="run-1",
            keep_failed_enrollments=True,
            stdout=StringIO(),
        )

        mock_bulk_unenroll.assert_called_once_with(
            [("a@b.com", "run-1")],
            keep_failed_enrollments=True,
        )

    def test_inline_users_mixed_results(self, mock_bulk_unenroll):
        """Command should display correct summary from bulk_unenroll_learners result"""
        mock_bulk_unenroll.return_value = {
            "succeeded": 1,
            "failed": 1,
            "skipped": 1,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Unenrolled: a@b.com from run-1"),
                ("b@c.com", "run-1", "failed", "Failed to unenroll b@c.com from run-1"),
                ("c@d.com", "run-1", "skipped", "No active enrollment for c@d.com in run-1"),
            ],
        }

        out = StringIO()
        err = StringIO()
        call_command(
            "unenroll_learners",
            users="a@b.com,b@c.com,c@d.com",
            run="run-1",
            stdout=out,
            stderr=err,
        )

        output = out.getvalue()
        assert "1 succeeded" in output
        assert "1 failed" in output
        assert "1 skipped" in output


@pytest.mark.django_db()
class TestBulkUnenrollCSV:
    """Tests for --csv flag"""

    def _write_csv(self, rows):
        """Write a CSV file and return its path"""
        f = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w", suffix=".csv", delete=False, newline=""
        )
        writer = csv.DictWriter(f, fieldnames=["user", "courseware_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        f.close()
        return f.name

    def test_csv_success(self, mock_bulk_unenroll):
        """CSV-based unenrollment should pass parsed entries to bulk_unenroll_learners"""
        mock_bulk_unenroll.return_value = {
            "succeeded": 2,
            "failed": 0,
            "skipped": 0,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Unenrolled: a@b.com from run-1"),
                ("c@d.com", "run-2", "succeeded", "Unenrolled: c@d.com from run-2"),
            ],
        }

        csv_path = self._write_csv([
            {"user": "a@b.com", "courseware_id": "run-1"},
            {"user": "c@d.com", "courseware_id": "run-2"},
        ])

        out = StringIO()
        call_command("unenroll_learners", csv=csv_path, stdout=out)

        mock_bulk_unenroll.assert_called_once_with(
            [("a@b.com", "run-1"), ("c@d.com", "run-2")],
            keep_failed_enrollments=False,
        )
        assert "2 succeeded" in out.getvalue()

    def test_csv_missing_columns(self):
        """CSV without required columns should raise CommandError"""
        f = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w", suffix=".csv", delete=False, newline=""
        )
        writer = csv.DictWriter(f, fieldnames=["email", "course"])
        writer.writeheader()
        writer.writerow({"email": "a@b.com", "course": "x"})
        f.close()

        with pytest.raises(CommandError, match="must have 'user' and 'courseware_id'"):
            call_command("unenroll_learners", csv=f.name, stdout=StringIO())

    def test_csv_file_not_found(self):
        """Non-existent CSV path should raise CommandError"""
        with pytest.raises(CommandError, match="CSV file not found"):
            call_command(
                "unenroll_learners", csv="/nonexistent/file.csv", stdout=StringIO()
            )

    def test_csv_skips_empty_rows(self, mock_bulk_unenroll):
        """Rows with empty user or courseware_id should not be passed to the util"""
        mock_bulk_unenroll.return_value = {
            "succeeded": 1,
            "failed": 0,
            "skipped": 0,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Unenrolled: a@b.com from run-1"),
            ],
        }

        csv_path = self._write_csv([
            {"user": "", "courseware_id": "course-v1:x+y+z"},
            {"user": "a@b.com", "courseware_id": "run-1"},
        ])

        out = StringIO()
        call_command("unenroll_learners", csv=csv_path, stdout=out)

        # Only the valid row should be passed
        mock_bulk_unenroll.assert_called_once_with(
            [("a@b.com", "run-1")],
            keep_failed_enrollments=False,
        )


@pytest.mark.django_db()
class TestBulkUnenrollDryRun:
    """Tests for --dry-run flag"""

    def test_dry_run_no_changes(self, mock_bulk_unenroll):
        """Dry run should not call bulk_unenroll_learners"""
        enrollment = CourseRunEnrollmentFactory.create(active=True)
        out = StringIO()
        call_command(
            "unenroll_learners",
            users=enrollment.user.email,
            run=enrollment.run.courseware_id,
            dry_run=True,
            stdout=out,
        )

        mock_bulk_unenroll.assert_not_called()
        output = out.getvalue()
        assert "DRY RUN" in output
        assert "Would unenroll" in output

    def test_dry_run_skips_inactive(self, mock_bulk_unenroll):
        """Dry run should report skipped for inactive enrollments"""
        enrollment = CourseRunEnrollmentFactory.create(active=False)
        out = StringIO()
        err = StringIO()
        call_command(
            "unenroll_learners",
            users=enrollment.user.email,
            run=enrollment.run.courseware_id,
            dry_run=True,
            stdout=out,
            stderr=err,
        )

        mock_bulk_unenroll.assert_not_called()
        assert "No active enrollment" in err.getvalue()

    def test_dry_run_user_not_found(self, mock_bulk_unenroll):
        """Dry run should report skipped for non-existent users"""
        run = CourseRunFactory.create()
        out = StringIO()
        err = StringIO()
        call_command(
            "unenroll_learners",
            users="nonexistent@example.com",
            run=run.courseware_id,
            dry_run=True,
            stdout=out,
            stderr=err,
        )

        mock_bulk_unenroll.assert_not_called()
        assert "User not found" in err.getvalue()


@pytest.mark.django_db()
class TestBulkUnenrollLearnersUtil:
    """Tests for the bulk_unenroll_learners utility function"""

    def test_successful_unenrollment(self, mocker):
        """Should unenroll active enrollments successfully"""
        from courses.management.utils import bulk_unenroll_learners

        enrollment = CourseRunEnrollmentFactory.create(active=True)
        mocker.patch(
            "courses.management.utils.deactivate_run_enrollment",
            return_value=enrollment,
        )

        result = bulk_unenroll_learners(
            [(enrollment.user.email, enrollment.run.courseware_id)]
        )

        assert result["succeeded"] == 1
        assert result["failed"] == 0
        assert result["skipped"] == 0

    def test_user_not_found(self):
        """Should skip when user doesn't exist"""
        from courses.management.utils import bulk_unenroll_learners

        run = CourseRunFactory.create()
        result = bulk_unenroll_learners(
            [("nonexistent@example.com", run.courseware_id)]
        )

        assert result["skipped"] == 1
        assert result["succeeded"] == 0

    def test_course_run_not_found(self):
        """Should skip when course run doesn't exist"""
        from courses.management.utils import bulk_unenroll_learners

        user = UserFactory.create()
        result = bulk_unenroll_learners(
            [(user.email, "course-v1:fake+fake+fake")]
        )

        assert result["skipped"] == 1
        assert result["succeeded"] == 0

    def test_no_active_enrollment(self):
        """Should skip when enrollment is inactive"""
        from courses.management.utils import bulk_unenroll_learners

        enrollment = CourseRunEnrollmentFactory.create(active=False)
        result = bulk_unenroll_learners(
            [(enrollment.user.email, enrollment.run.courseware_id)]
        )

        assert result["skipped"] == 1
        assert result["succeeded"] == 0

    def test_deactivation_failure(self, mocker):
        """Should count as failed when deactivate_run_enrollment returns None"""
        from courses.management.utils import bulk_unenroll_learners

        enrollment = CourseRunEnrollmentFactory.create(active=True)
        mocker.patch(
            "courses.management.utils.deactivate_run_enrollment",
            return_value=None,
        )

        result = bulk_unenroll_learners(
            [(enrollment.user.email, enrollment.run.courseware_id)]
        )

        assert result["failed"] == 1
        assert result["succeeded"] == 0

    def test_keep_failed_enrollments_passed(self, mocker):
        """Should pass keep_failed_enrollments to deactivate_run_enrollment"""
        from courses.management.utils import bulk_unenroll_learners

        enrollment = CourseRunEnrollmentFactory.create(active=True)
        mock_deactivate = mocker.patch(
            "courses.management.utils.deactivate_run_enrollment",
            return_value=enrollment,
        )

        bulk_unenroll_learners(
            [(enrollment.user.email, enrollment.run.courseware_id)],
            keep_failed_enrollments=True,
        )

        mock_deactivate.assert_called_once()
        assert mock_deactivate.call_args[1]["keep_failed_enrollments"] is True
