"""Tests for enroll_learners management command"""

import csv
import tempfile
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from courses.factories import CourseRunFactory
from users.factories import UserFactory


@pytest.fixture
def mock_bulk_enroll(mocker):
    """Mock bulk_enroll_learners to avoid edX API calls"""
    return mocker.patch(
        "courses.management.commands.enroll_learners.bulk_enroll_learners",
        return_value={
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        },
    )


@pytest.mark.django_db()
class TestBulkEnrollInlineUsers:
    """Tests for --users flag"""

    def test_inline_users_success(self, mock_bulk_enroll):
        """Enrolling inline users should call bulk_enroll_learners with correct entries"""
        mock_bulk_enroll.return_value = {
            "succeeded": 2,
            "failed": 0,
            "skipped": 0,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Enrolled a@b.com in run-1"),
                ("c@d.com", "run-1", "succeeded", "Enrolled c@d.com in run-1"),
            ],
        }

        out = StringIO()
        call_command(
            "enroll_learners",
            users="a@b.com,c@d.com",
            run="run-1",
            commit=True,
            stdout=out,
        )

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1"), ("c@d.com", "run-1")],
            mode="audit",
            keep_failed_enrollments=False,
        )
        output = out.getvalue()
        assert "2 succeeded" in output
        assert "0 failed" in output

    def test_inline_users_missing_run(self):
        """--users without --run should raise CommandError"""
        with pytest.raises(CommandError, match="--run is required"):
            call_command("enroll_learners", users="user@example.com")

    def test_inline_users_keep_failed_enrollments(self, mock_bulk_enroll):
        """--keep-failed-enrollments flag should be passed through"""
        call_command(
            "enroll_learners",
            users="a@b.com",
            run="run-1",
            keep_failed_enrollments=True,
            commit=True,
            stdout=StringIO(),
        )

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1")],
            mode="audit",
            keep_failed_enrollments=True,
        )

    def test_inline_users_mode_passed(self, mock_bulk_enroll):
        """--mode flag should be passed through"""
        call_command(
            "enroll_learners",
            users="a@b.com",
            run="run-1",
            mode="verified",
            commit=True,
            stdout=StringIO(),
        )

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1")],
            mode="verified",
            keep_failed_enrollments=False,
        )

    def test_inline_users_mixed_results(self, mock_bulk_enroll):
        """Command should display correct summary from bulk_enroll_learners result"""
        mock_bulk_enroll.return_value = {
            "succeeded": 1,
            "failed": 1,
            "skipped": 1,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Enrolled a@b.com in run-1"),
                ("b@c.com", "run-1", "failed", "Failed to enroll b@c.com in run-1"),
                ("c@d.com", "run-1", "skipped", "User not found: c@d.com"),
            ],
        }

        out = StringIO()
        err = StringIO()
        call_command(
            "enroll_learners",
            users="a@b.com,b@c.com,c@d.com",
            run="run-1",
            commit=True,
            stdout=out,
            stderr=err,
        )

        output = out.getvalue()
        assert "1 succeeded" in output
        assert "1 failed" in output
        assert "1 skipped" in output


@pytest.mark.django_db()
class TestBulkEnrollCSV:
    """Tests for --csv flag"""

    def _write_csv(self, rows, fieldnames):
        """Write a CSV file and return its path"""
        f = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w", suffix=".csv", delete=False, newline=""
        )
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        f.close()
        return f.name

    def test_csv_email_column_with_run_flag(self, mock_bulk_enroll):
        """A CSV with just an 'email' column should use --run for every row"""
        mock_bulk_enroll.return_value = {
            "succeeded": 2,
            "failed": 0,
            "skipped": 0,
            "details": [
                ("a@b.com", "run-1", "succeeded", "Enrolled a@b.com in run-1"),
                ("c@d.com", "run-1", "succeeded", "Enrolled c@d.com in run-1"),
            ],
        }

        csv_path = self._write_csv(
            [{"email": "a@b.com"}, {"email": "c@d.com"}], fieldnames=["email"]
        )

        out = StringIO()
        call_command(
            "enroll_learners", csv=csv_path, run="run-1", commit=True, stdout=out
        )

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1"), ("c@d.com", "run-1")],
            mode="audit",
            keep_failed_enrollments=False,
        )
        assert "2 succeeded" in out.getvalue()

    def test_csv_accepts_user_column_alias(self, mock_bulk_enroll):
        """A CSV with a 'user' column (instead of 'email') should also work"""
        csv_path = self._write_csv([{"user": "a@b.com"}], fieldnames=["user"])

        call_command(
            "enroll_learners",
            csv=csv_path,
            run="run-1",
            commit=True,
            stdout=StringIO(),
        )

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1")],
            mode="audit",
            keep_failed_enrollments=False,
        )

    def test_csv_own_courseware_id_column(self, mock_bulk_enroll):
        """A CSV with its own courseware_id column shouldn't require --run"""
        csv_path = self._write_csv(
            [
                {"email": "a@b.com", "courseware_id": "run-1"},
                {"email": "c@d.com", "courseware_id": "run-2"},
            ],
            fieldnames=["email", "courseware_id"],
        )

        call_command("enroll_learners", csv=csv_path, commit=True, stdout=StringIO())

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1"), ("c@d.com", "run-2")],
            mode="audit",
            keep_failed_enrollments=False,
        )

    def test_csv_missing_email_column(self):
        """CSV without a recognized email column should raise CommandError"""
        csv_path = self._write_csv([{"name": "a"}], fieldnames=["name"])

        with pytest.raises(CommandError, match="must have an email column"):
            call_command(
                "enroll_learners", csv=csv_path, run="run-1", stdout=StringIO()
            )

    def test_csv_without_run_or_courseware_column(self):
        """CSV with no courseware_id column and no --run should raise CommandError"""
        csv_path = self._write_csv([{"email": "a@b.com"}], fieldnames=["email"])

        with pytest.raises(CommandError, match="--run is required"):
            call_command("enroll_learners", csv=csv_path, stdout=StringIO())

    def test_csv_file_not_found(self):
        """Non-existent CSV path should raise CommandError"""
        with pytest.raises(CommandError, match="CSV file not found"):
            call_command(
                "enroll_learners",
                csv="/nonexistent/file.csv",
                run="run-1",
                stdout=StringIO(),
            )

    def test_csv_skips_empty_rows(self, mock_bulk_enroll):
        """Rows with an empty email should not be passed to the util"""
        csv_path = self._write_csv(
            [{"email": ""}, {"email": "a@b.com"}], fieldnames=["email"]
        )

        out = StringIO()
        call_command(
            "enroll_learners", csv=csv_path, run="run-1", commit=True, stdout=out
        )

        mock_bulk_enroll.assert_called_once_with(
            [("a@b.com", "run-1")],
            mode="audit",
            keep_failed_enrollments=False,
        )


@pytest.mark.django_db()
class TestBulkEnrollDryRun:
    """Tests for default dry-run behavior (no --commit flag)"""

    def test_default_is_dry_run(self, mock_bulk_enroll):
        """Without --commit, command should run in dry-run mode"""
        user = UserFactory.create()
        run = CourseRunFactory.create()
        out = StringIO()
        call_command(
            "enroll_learners",
            users=user.email,
            run=run.courseware_id,
            stdout=out,
        )

        mock_bulk_enroll.assert_not_called()
        output = out.getvalue()
        assert "DRY RUN" in output
        assert "Would enroll" in output
        assert "Re-run with --commit" in output

    def test_dry_run_user_not_found(self, mock_bulk_enroll):
        """Dry run should report skipped for non-existent users"""
        run = CourseRunFactory.create()
        out = StringIO()
        err = StringIO()
        call_command(
            "enroll_learners",
            users="nonexistent@example.com",
            run=run.courseware_id,
            stdout=out,
            stderr=err,
        )

        mock_bulk_enroll.assert_not_called()
        assert "User not found" in err.getvalue()

    def test_dry_run_course_run_not_found(self, mock_bulk_enroll):
        """Dry run should report skipped for a non-existent course run"""
        user = UserFactory.create()
        out = StringIO()
        err = StringIO()
        call_command(
            "enroll_learners",
            users=user.email,
            run="course-v1:fake+fake+fake",
            stdout=out,
            stderr=err,
        )

        mock_bulk_enroll.assert_not_called()
        assert "Course run not found" in err.getvalue()


@pytest.mark.django_db()
class TestBulkEnrollNoArgs:
    """Tests for missing arguments"""

    def test_no_args_raises_error(self):
        """Command with no arguments should raise CommandError"""
        with pytest.raises(CommandError, match="Provide --csv or --users"):
            call_command("enroll_learners", stdout=StringIO())

    def test_csv_with_users_raises_error(self):
        """--csv combined with --users should raise CommandError"""
        with pytest.raises(CommandError, match="--csv cannot be combined"):
            call_command(
                "enroll_learners",
                csv="file.csv",
                users="a@b.com",
                stdout=StringIO(),
            )

    def test_invalid_mode_raises_error(self):
        """An unsupported --mode value should raise CommandError"""
        # Choice validation only runs against argv-style invocation, not
        # against kwargs passed directly to call_command.
        with pytest.raises(CommandError, match="invalid choice: 'bogus'"):
            call_command(
                "enroll_learners", "--users=a@b.com", "--run=run-1", "--mode=bogus"
            )
