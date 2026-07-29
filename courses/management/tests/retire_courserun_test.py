"""Tests for the retire_courserun management command and courses.retirement."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from mitol.common.utils.datetime import now_in_utc

from b2b.api import (
    RetirementContractCollisionError,
    get_or_create_retirement_contract,
    move_run_to_retirement_contract,
)
from b2b.factories import ContractPageFactory
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
)
from courses.retirement import (
    SourceRunRetirementError,
    check_run_retirable,
    compute_retirement_dates,
    deactivate_run_products,
    get_run_products,
    push_run_dates_to_edx,
    retire_course_run,
)
from ecommerce.factories import ProductFactory
from ecommerce.models import Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_edx(mocker):
    """Stub out both edX calls the command makes."""

    return {
        "update": mocker.patch("courses.retirement.update_edx_course"),
        "get": mocker.patch("courses.retirement.get_edx_course"),
        "verify_get": mocker.patch(
            "courses.management.commands.retire_courserun.get_edx_course"
        ),
    }


@pytest.fixture
def run():
    """A live, in-progress run with a product."""

    course_run = CourseRunFactory.create(live=True)
    ProductFactory.create(purchasable_object=course_run, is_active=True)
    return course_run


def _run_command(course_run, tmp_path, **kwargs):
    """Call the command, keeping snapshots out of the repo."""

    out = StringIO()
    err = StringIO()
    call_command(
        "retire_courserun",
        run=course_run.courseware_id,
        snapshot_dir=str(tmp_path),
        stdout=out,
        stderr=err,
        **kwargs,
    )
    return out.getvalue(), err.getvalue()


class TestDryRun:
    """Without --commit, nothing anywhere should change."""

    def test_dry_run_changes_nothing(self, run, tmp_path, mock_edx):
        """Dry run changes nothing."""

        original = (
            run.live,
            run.start_date,
            run.end_date,
            run.enrollment_start,
            run.enrollment_end,
        )

        out, _ = _run_command(run, tmp_path)

        run.refresh_from_db()
        assert (
            run.live,
            run.start_date,
            run.end_date,
            run.enrollment_start,
            run.enrollment_end,
        ) == original
        assert all(p.is_active for p in get_run_products(run))
        mock_edx["update"].assert_not_called()
        assert "DRY RUN" in out

    def test_dry_run_still_writes_a_snapshot(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Dry run still writes a snapshot."""

        _run_command(run, tmp_path)

        snapshots = list(tmp_path.glob("retire_*.json"))
        assert len(snapshots) == 1

    def test_dry_run_reports_enrollments_and_products(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Dry run reports enrollments and products."""

        enrollment = CourseRunEnrollmentFactory.create(run=run, active=True)

        out, _ = _run_command(run, tmp_path)

        assert enrollment.user.email in out
        assert "1 active" in out
        assert "Products:     1" in out


class TestGuards:
    """The command should refuse the dangerous cases."""

    def test_unknown_run(self, tmp_path):
        """Unknown run."""

        with pytest.raises(CommandError, match="Could not find course run"):
            call_command(
                "retire_courserun",
                run="course-v1:nope+nope+nope",
                snapshot_dir=str(tmp_path),
            )

    def test_source_run_refused(self, tmp_path, mock_edx):  # noqa: ARG002
        """Source run refused."""

        source = CourseRunFactory.create(is_source_run=True)

        with pytest.raises(CommandError, match="is a source run"):
            _run_command(source, tmp_path, commit=True)

    def test_source_run_refused_in_dry_run_too(self, tmp_path, mock_edx):  # noqa: ARG002
        """Source run refused in dry run too."""

        source = CourseRunFactory.create(is_source_run=True)

        with pytest.raises(CommandError, match="is a source run"):
            _run_command(source, tmp_path)

    def test_source_run_by_run_tag_refused(self):
        """Source run by run tag refused."""

        source = CourseRunFactory.create(is_source_run=False, run_tag="SOURCE")

        with pytest.raises(SourceRunRetirementError):
            check_run_retirable(source)

    def test_active_enrollments_do_not_block_retirement(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Retiring never blocks on enrollments; it leaves them intact."""

        enrollment = CourseRunEnrollmentFactory.create(run=run, active=True)

        _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        enrollment.refresh_from_db()
        assert run.live is False
        # No view filters enrollments on live/end_date/expiration_date, and edX
        # access is enrollment-based, so this learner keeps working access.
        assert enrollment.active is True

    def test_unenroll_blocked_by_active_enrollments(self, run, tmp_path, mock_edx):
        """--unenroll refuses without the override, changing nothing."""

        CourseRunEnrollmentFactory.create(run=run, active=True)

        with pytest.raises(CommandError, match="--unenroll would remove"):
            _run_command(run, tmp_path, commit=True, unenroll=True)

        run.refresh_from_db()
        assert run.live is True
        mock_edx["update"].assert_not_called()

    def test_unenroll_allowed_with_override(self, run, tmp_path, mock_edx, mocker):  # noqa: ARG002
        """--allow-active-enrollments unblocks --unenroll."""

        mock_bulk = mocker.patch(
            "courses.management.commands.retire_courserun.bulk_unenroll_learners",
            return_value={"succeeded": 1, "failed": 0, "skipped": 0, "details": []},
        )
        CourseRunEnrollmentFactory.create(run=run, active=True)

        _run_command(
            run, tmp_path, commit=True, unenroll=True, allow_active_enrollments=True
        )

        run.refresh_from_db()
        assert run.live is False
        mock_bulk.assert_called_once()

    def test_unenroll_with_no_active_enrollments_needs_no_override(
        self,
        run,
        tmp_path,
        mock_edx,  # noqa: ARG002
    ):
        """--unenroll on a run nobody is on doesn't need the override."""

        CourseRunEnrollmentFactory.create(run=run, active=False)

        _run_command(run, tmp_path, commit=True, unenroll=True)

        run.refresh_from_db()
        assert run.live is False

    def test_inactive_enrollments_do_not_block(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Inactive enrollments do not block."""

        CourseRunEnrollmentFactory.create(run=run, active=False)

        _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        assert run.live is False


class TestCommit:
    """The committed path."""

    def test_dates_and_live(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Committing pushes the windows into the past and unsets live."""

        _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        now = now_in_utc()
        assert run.live is False
        assert run.end_date < now
        assert run.enrollment_end < now
        assert run.start_date < run.end_date
        assert run.enrollment_start <= run.start_date

    def test_future_expiration_date_untouched(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """A future expiration_date is left alone."""

        original = run.expiration_date
        assert original > now_in_utc()

        _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        # Moving expiration_date would hide the run from the dashboards of
        # learners we deliberately left enrolled.
        assert run.expiration_date == original

    def test_past_expiration_date_is_cleared(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """A past expiration_date is cleared instead of tripping clean()."""

        # CourseRun.save() calls clean(), which rejects an expiration_date
        # earlier than start/end. Without clearing it, retiring an already
        # finished run raises ValidationError *after* the edX write landed.
        #
        # The setup itself has to satisfy clean(), so the whole run is pushed
        # well into the past: start < end < expiration, all historic. Retiring
        # then moves end to yesterday, which lands after expiration and is what
        # forces the reset.
        now = now_in_utc()
        run.start_date = now - timedelta(days=200)
        run.end_date = now - timedelta(days=120)
        run.expiration_date = now - timedelta(days=90)
        run.save()

        _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        assert run.expiration_date is None
        assert run.live is False

    def test_products_deactivated(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Products deactivated."""

        _run_command(run, tmp_path, commit=True)

        assert all(not p.is_active for p in get_run_products(run))

    def test_keep_products(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """Keep products."""

        _run_command(run, tmp_path, commit=True, keep_products=True)

        assert all(p.is_active for p in get_run_products(run))

    def test_edx_gets_a_complete_date_set(self, run, tmp_path, mock_edx):
        """All four dates must reach edX or the sync will revert us."""

        _run_command(run, tmp_path, commit=True)

        mock_edx["update"].assert_called_once()
        _args, kwargs = mock_edx["update"].call_args
        for key in ("start", "end", "enrollment_start", "enrollment_end"):
            assert kwargs[key] is not None
        assert kwargs["end"] < now_in_utc()

    def test_edx_failure_leaves_local_state_alone(self, run, tmp_path, mock_edx):
        """A failed edX write must abort before anything local changes."""

        mock_edx["update"].side_effect = ValueError("edX exploded")

        with pytest.raises(ValueError, match="edX exploded"):
            _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        assert run.live is True
        assert all(p.is_active for p in get_run_products(run))

    def test_skip_edx(self, run, tmp_path, mock_edx):
        """--skip-edx bypasses edX entirely."""

        _run_command(run, tmp_path, commit=True, skip_edx=True)

        mock_edx["update"].assert_not_called()
        run.refresh_from_db()
        assert run.live is False

    def test_unenroll(self, run, tmp_path, mock_edx, mocker):  # noqa: ARG002
        """--unenroll defaults to sending no email."""

        mock_bulk = mocker.patch(
            "courses.management.commands.retire_courserun.bulk_unenroll_learners",
            return_value={"succeeded": 1, "failed": 0, "skipped": 0, "details": []},
        )
        enrollment = CourseRunEnrollmentFactory.create(run=run, active=True)

        _run_command(
            run,
            tmp_path,
            commit=True,
            allow_active_enrollments=True,
            unenroll=True,
        )

        mock_bulk.assert_called_once_with(
            [(enrollment.user.email, run.courseware_id)],
            keep_failed_enrollments=False,
            send_notification=False,
        )

    def test_unenroll_with_email(self, run, tmp_path, mock_edx, mocker):  # noqa: ARG002
        """--email opts into notifying learners."""

        mock_bulk = mocker.patch(
            "courses.management.commands.retire_courserun.bulk_unenroll_learners",
            return_value={"succeeded": 1, "failed": 0, "skipped": 0, "details": []},
        )
        CourseRunEnrollmentFactory.create(run=run, active=True)

        _run_command(
            run,
            tmp_path,
            commit=True,
            allow_active_enrollments=True,
            unenroll=True,
            email=True,
        )

        assert mock_bulk.call_args.kwargs["send_notification"] is True


class TestContractHandling:
    """Retired B2B runs get parked, not orphaned."""

    def test_moved_to_holding_contract(self, tmp_path, mock_edx):  # noqa: ARG002
        """A retired B2B run is parked, never orphaned."""

        contract = ContractPageFactory.create()
        course_run = CourseRunFactory.create(live=True, b2b_contract=contract)

        _run_command(course_run, tmp_path, commit=True)

        course_run.refresh_from_db()
        holding = get_or_create_retirement_contract()
        assert course_run.b2b_contract_id == holding.id
        # Never nulled - a null contract FK would make this a public-catalog run.
        assert course_run.b2b_contract_id is not None
        assert holding.active is False
        assert holding.live is False

    def test_holding_contract_is_reused(self, tmp_path, mock_edx):  # noqa: ARG002
        """The holding contract is created once and reused."""

        contract = ContractPageFactory.create()
        first = CourseRunFactory.create(live=True, b2b_contract=contract)
        second = CourseRunFactory.create(live=True, b2b_contract=contract)

        _run_command(first, tmp_path, commit=True)
        _run_command(second, tmp_path, commit=True)

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.b2b_contract_id == second.b2b_contract_id

    def test_keep_contract(self, tmp_path, mock_edx):  # noqa: ARG002
        """Keep contract."""

        contract = ContractPageFactory.create()
        course_run = CourseRunFactory.create(live=True, b2b_contract=contract)

        _run_command(course_run, tmp_path, commit=True, keep_contract=True)

        course_run.refresh_from_db()
        assert course_run.b2b_contract_id == contract.id

    def test_non_b2b_run_needs_no_contract(self, run, tmp_path, mock_edx):  # noqa: ARG002
        """A non-B2B run retires fine with no contract step."""

        _run_command(run, tmp_path, commit=True)

        run.refresh_from_db()
        assert run.b2b_contract_id is None
        assert run.live is False

    def test_keep_products_refused_when_parking_the_run(self, tmp_path, mock_edx):  # noqa: ARG002
        """--keep-products can't be combined with the contract move."""

        contract = ContractPageFactory.create()
        course_run = CourseRunFactory.create(live=True, b2b_contract=contract)
        ProductFactory.create(purchasable_object=course_run, is_active=True)

        with pytest.raises(CommandError, match="--keep-products cannot be combined"):
            _run_command(course_run, tmp_path, commit=True, keep_products=True)

        course_run.refresh_from_db()
        assert course_run.b2b_contract_id == contract.id
        assert course_run.live is True

    def test_keep_products_allowed_with_keep_contract(self, tmp_path, mock_edx):  # noqa: ARG002
        """--keep-contract makes --keep-products safe again."""

        contract = ContractPageFactory.create()
        course_run = CourseRunFactory.create(live=True, b2b_contract=contract)
        ProductFactory.create(purchasable_object=course_run, is_active=True)

        _run_command(
            course_run,
            tmp_path,
            commit=True,
            keep_products=True,
            keep_contract=True,
        )

        course_run.refresh_from_db()
        assert course_run.live is False
        assert course_run.b2b_contract_id == contract.id
        assert all(p.is_active for p in get_run_products(course_run))


class TestCollisionCheck:
    """The holding contract can't be allowed to violate a unique constraint."""

    @pytest.fixture
    def source_contract(self):
        """
        A normal contract, created before anything asks for the holding one.

        ContractPageFactory bootstraps HomePage -> OrganizationIndexPage ->
        OrganizationPage. get_or_create_retirement_contract() falls back to
        ensure_b2b_organization_index(), which calls cms.api.get_home_page() and
        raises Page.DoesNotExist when no Wagtail tree exists yet, so the ordering
        matters.
        """

        return ContractPageFactory.create()

    def test_language_collision_refused(self, source_contract, mock_edx):  # noqa: ARG002
        """A parked run with the same course/tag/language/variant blocks the move."""

        holding = get_or_create_retirement_contract()
        parked = CourseRunFactory.create(
            b2b_contract=holding, language="de_DE", run_tag="1T9C2026"
        )
        incoming = CourseRunFactory.create(
            course=parked.course,
            b2b_contract=source_contract,
            language="de_DE",
            run_tag="1T9C2026",
        )

        with pytest.raises(RetirementContractCollisionError, match="already parked"):
            move_run_to_retirement_contract(incoming)

    def test_primary_language_collision_refused(self, source_contract, mock_edx):  # noqa: ARG002
        """A parked primary-language run blocks another for the same group."""

        holding = get_or_create_retirement_contract()
        parked = CourseRunFactory.create(
            b2b_contract=holding,
            language="",
            is_primary_language=True,
            run_tag="1T9C2026",
        )
        incoming = CourseRunFactory.create(
            course=parked.course,
            b2b_contract=source_contract,
            language="",
            is_primary_language=True,
            run_tag="1T9C2026",
        )

        with pytest.raises(RetirementContractCollisionError, match="primary-language"):
            move_run_to_retirement_contract(incoming)

    def test_distinct_run_tags_do_not_collide(self, source_contract, mock_edx):  # noqa: ARG002
        """Different run tags park side by side, which is the normal case."""

        holding = get_or_create_retirement_contract()
        parked = CourseRunFactory.create(
            b2b_contract=holding, language="de_DE", run_tag="1T9C2026"
        )
        incoming = CourseRunFactory.create(
            course=parked.course,
            b2b_contract=source_contract,
            language="de_DE",
            run_tag="1T9C2027",
        )

        assert move_run_to_retirement_contract(incoming).id == holding.id

    def test_already_parked_run_is_a_no_op(self, source_contract, mock_edx):  # noqa: ARG002
        """Re-parking a run that's already in the holding contract is fine."""

        holding = get_or_create_retirement_contract()
        parked = CourseRunFactory.create(b2b_contract=holding, run_tag="1T9C2026")

        assert move_run_to_retirement_contract(parked).id == holding.id


class TestRetirementHelpers:
    """Unit coverage for the shared util."""

    def test_compute_dates_puts_everything_in_the_past(self):
        """Every computed date lands in the past, in a valid order."""

        course_run = CourseRunFactory.build(
            start_date=None, end_date=None, enrollment_start=None, enrollment_end=None
        )

        dates = compute_retirement_dates(course_run)

        now = now_in_utc()
        assert dates["end"] < now
        assert dates["enrollment_end"] < now
        assert dates["start"] < dates["end"]
        assert dates["enrollment_start"] <= dates["start"]

    def test_compute_dates_preserves_an_early_start(self):
        """An already-past start date is left alone."""

        # Pinned rather than left to the factory: its upper bound is now-1d,
        # which is exactly the cutoff compute_retirement_dates compares against.
        original_start = now_in_utc() - timedelta(days=10)
        course_run = CourseRunFactory.build(start_date=original_start)

        dates = compute_retirement_dates(course_run)

        assert dates["start"] == original_start

    def test_push_dates_reports_incomplete_sets(self, run, mock_edx):
        """A run with no end_date can't have its enrollment window set in edX."""

        run.end_date = None
        run.save()

        assert push_run_dates_to_edx(run) is False

        kwargs = mock_edx["update"].call_args.kwargs
        assert "enrollment_end" not in kwargs

    def test_push_dates_sends_a_complete_set(self, run, mock_edx):
        """A complete date set reaches edX intact."""

        dates = compute_retirement_dates(run)

        assert push_run_dates_to_edx(run, dates) is True

        kwargs = mock_edx["update"].call_args.kwargs
        assert kwargs["enrollment_end"] == dates["enrollment_end"]

    def test_get_run_products_sees_inactive_products(self, run):
        """get_run_products must see products the default manager hides."""

        product = get_run_products(run)[0]
        product.is_active = False
        product.save()

        assert len(get_run_products(run)) == 1
        assert not Product.objects.filter(id=product.id).exists()

    def test_deactivate_run_products_is_idempotent(self, run):
        """Deactivate run products is idempotent."""

        assert len(deactivate_run_products(run)) == 1
        assert deactivate_run_products(run) == []

    def test_retire_leaves_enrollments_alone(self, run, mock_edx):  # noqa: ARG002
        """Retire leaves enrollments alone."""

        enrollment = CourseRunEnrollmentFactory.create(run=run, active=True)

        retire_course_run(run)

        enrollment.refresh_from_db()
        assert enrollment.active is True
        assert enrollment.change_status is None

    def test_retire_returns_what_it_changed(self, run, mock_edx):  # noqa: ARG002
        """Retire returns what it changed."""

        result = retire_course_run(run)

        assert result["edx_updated"] is True
        assert len(result["products"]) == 1
        assert set(result["dates"]) == {
            "start",
            "end",
            "enrollment_start",
            "enrollment_end",
        }
