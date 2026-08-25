"""Tests for unenroll_by_country management command"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from courses.factories import CourseRunEnrollmentFactory, CourseRunFactory
from users.factories import UserFactory


@pytest.fixture
def mock_bulk_unenroll(mocker):
    """Mock bulk_unenroll_learners to avoid edX API calls"""
    return mocker.patch(
        "courses.management.commands.unenroll_by_country.bulk_unenroll_learners",
        return_value={
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "details": [],
        },
    )


def _enrollment_for_country(country, **kwargs):
    """Create an active CourseRunEnrollment for a user whose legal address is in `country`"""
    user = UserFactory.create()  # UserFactory creates a legal_address via RelatedFactory
    user.legal_address.country = country
    user.legal_address.save()
    return CourseRunEnrollmentFactory.create(user=user, active=True, **kwargs)


@pytest.mark.django_db()
class TestUnenrollByCountry:
    """Tests for --country flag"""

    def test_country_success(self, mock_bulk_unenroll):
        """Unenrolling by country should call bulk_unenroll_learners with matching entries"""
        e1 = _enrollment_for_country("IR")
        e2 = _enrollment_for_country("IR")
        _enrollment_for_country("US")  # different country, excluded

        mock_bulk_unenroll.return_value = {
            "succeeded": 2,
            "failed": 0,
            "skipped": 0,
            "details": [
                (
                    e1.user.email,
                    e1.run.courseware_id,
                    "succeeded",
                    f"Unenrolled: {e1.user.email} from {e1.run.courseware_id}",
                ),
                (
                    e2.user.email,
                    e2.run.courseware_id,
                    "succeeded",
                    f"Unenrolled: {e2.user.email} from {e2.run.courseware_id}",
                ),
            ],
        }

        out = StringIO()
        call_command("unenroll_by_country", country="IR", commit=True, stdout=out)

        call_args = mock_bulk_unenroll.call_args
        entries = call_args[0][0]
        emails = {e[0] for e in entries}
        assert emails == {e1.user.email, e2.user.email}
        mock_bulk_unenroll.assert_called_once_with(
            entries,
            keep_failed_enrollments=False,
            send_notification=True,
        )
        output = out.getvalue()
        assert "2 succeeded" in output

    def test_country_is_case_insensitive(self, mock_bulk_unenroll):
        """Lowercase country codes should be normalized before filtering"""
        enrollment = _enrollment_for_country("IR")

        call_command(
            "unenroll_by_country", country="ir", commit=True, stdout=StringIO()
        )

        entries = mock_bulk_unenroll.call_args[0][0]
        assert entries == [(enrollment.user.email, enrollment.run.courseware_id)]

    def test_invalid_country_code(self):
        """A country code that isn't 2 characters should raise CommandError"""
        with pytest.raises(CommandError, match="ISO 3166-1 alpha-2"):
            call_command(
                "unenroll_by_country", country="IRAN", stdout=StringIO()
            )

    def test_no_matching_enrollments(self):
        """A country with no active enrollments should raise CommandError"""
        with pytest.raises(CommandError, match="No active enrollments found"):
            call_command(
                "unenroll_by_country", country="IR", commit=True, stdout=StringIO()
            )

    def test_excludes_inactive_enrollments(self):
        """Inactive enrollments should not be counted"""
        _enrollment_for_country("IR", active=False)

        with pytest.raises(CommandError, match="No active enrollments found"):
            call_command(
                "unenroll_by_country", country="IR", commit=True, stdout=StringIO()
            )

    def test_scoped_to_run(self, mock_bulk_unenroll):
        """--run should restrict entries to that course run only"""
        run = CourseRunFactory.create()
        other_run = CourseRunFactory.create()
        matching = _enrollment_for_country("IR", run=run)
        _enrollment_for_country("IR", run=other_run)

        call_command(
            "unenroll_by_country",
            country="IR",
            run=run.courseware_id,
            commit=True,
            stdout=StringIO(),
        )

        entries = mock_bulk_unenroll.call_args[0][0]
        assert entries == [(matching.user.email, run.courseware_id)]

    def test_keep_failed_enrollments_passed(self, mock_bulk_unenroll):
        """--keep-failed-enrollments flag should be passed through"""
        _enrollment_for_country("IR")

        call_command(
            "unenroll_by_country",
            country="IR",
            keep_failed_enrollments=True,
            commit=True,
            stdout=StringIO(),
        )

        mock_bulk_unenroll.assert_called_once()
        assert mock_bulk_unenroll.call_args[1]["keep_failed_enrollments"] is True

    def test_no_email_flag(self, mock_bulk_unenroll):
        """--no-email should pass send_notification=False"""
        _enrollment_for_country("IR")

        call_command(
            "unenroll_by_country",
            country="IR",
            commit=True,
            no_email=True,
            stdout=StringIO(),
        )

        mock_bulk_unenroll.assert_called_once()
        assert mock_bulk_unenroll.call_args[1]["send_notification"] is False


@pytest.mark.django_db()
class TestUnenrollByCountryDryRun:
    """Tests for default dry-run behavior (no --commit flag)"""

    def test_default_is_dry_run(self, mock_bulk_unenroll):
        """Without --commit, command should run in dry-run mode"""
        enrollment = _enrollment_for_country("IR")

        out = StringIO()
        call_command("unenroll_by_country", country="IR", stdout=out)

        mock_bulk_unenroll.assert_not_called()
        output = out.getvalue()
        assert "DRY RUN" in output
        assert f"Would unenroll: {enrollment.user.email}" in output
        assert "Re-run with --commit" in output
