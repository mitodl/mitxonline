"""Tests for the backfill_program_certificate_titles management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from cms.factories import ProgramPageFactory
from cms.models import CertificatePage
from courses.factories import ProgramCertificateFactory
from courses.models import Program, ProgramCertificate

pytestmark = [pytest.mark.django_db]


def _program_with_issued_cert(frozen_title, live_title):
    """Create a program whose issued certificate is frozen to ``frozen_title``
    while the live CMS certificate page now shows ``live_title``.

    Returns ``(program, certificate)``.
    """
    program_page = ProgramPageFactory.create()
    cert_page = program_page.certificate_page

    # Freeze a revision carrying the old title, then issue a cert against it.
    cert_page.product_name = frozen_title
    cert_page.save()
    cert_page.save_revision()
    certificate = ProgramCertificateFactory.create(
        program=program_page.program,
        certificate_page_revision=cert_page.revisions.last(),
    )

    # The admin has since corrected the live "Certificate Title".
    cert_page.product_name = live_title
    cert_page.save()

    return program_page.program, certificate


def _run(*args):
    out = StringIO()
    call_command("backfill_program_certificate_titles", *args, stdout=out, stderr=out)
    return out.getvalue()


def _frozen_title(certificate):
    revision = certificate.certificate_page_revision
    revision.refresh_from_db()
    return revision.as_object().product_name


def test_commit_updates_frozen_title_to_live_page_value():
    """--commit rewrites each issued cert's frozen product_name to the live title."""
    program, certificate = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="NEW Title"
    )

    _run("--program", program.readable_id, "--commit")

    assert _frozen_title(certificate) == "NEW Title"


def test_dry_run_by_default_makes_no_db_changes():
    """Without --commit the command reports but never writes to the DB."""
    program, certificate = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="NEW Title"
    )

    _run("--program", program.readable_id)

    assert _frozen_title(certificate) == "OLD Title"


def test_dry_run_output_reports_planned_change():
    """Dry-run output names the program, the old and new titles, and the mode."""
    program, _ = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="NEW Title"
    )

    output = _run("--program", program.readable_id)

    assert "DRY RUN" in output
    assert program.readable_id in output
    assert "OLD Title" in output
    assert "NEW Title" in output


def test_commit_is_idempotent():
    """A second --commit run is a no-op: the revision is reported as skipped."""
    program, certificate = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="NEW Title"
    )

    _run("--program", program.readable_id, "--commit")
    output = _run("--program", program.readable_id, "--commit")

    assert _frozen_title(certificate) == "NEW Title"
    assert "skipped" in output
    assert "[changed]" not in output
    assert "0 revision(s) changed" in output


def test_null_revision_cert_is_skipped_without_error():
    """A certificate with no frozen revision (e.g. revoked) is left untouched."""
    program, certificate = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="NEW Title"
    )
    ProgramCertificate.objects.filter(pk=certificate.pk).update(
        certificate_page_revision=None
    )

    _run("--program", program.readable_id, "--commit")

    certificate.refresh_from_db()
    assert certificate.certificate_page_revision is None


def test_shared_revision_updated_once_for_all_certs():
    """Certs issued at the same page revision share one Revision row: a single
    edit updates them all, and the report counts the certs.
    """
    program_page = ProgramPageFactory.create()
    cert_page = program_page.certificate_page
    cert_page.product_name = "OLD Title"
    cert_page.save()
    cert_page.save_revision()
    revision = cert_page.revisions.last()

    cert_a = ProgramCertificateFactory.create(
        program=program_page.program, certificate_page_revision=revision
    )
    cert_b = ProgramCertificateFactory.create(
        program=program_page.program, certificate_page_revision=revision
    )

    cert_page.product_name = "NEW Title"
    cert_page.save()

    output = _run("--program", program_page.program.readable_id, "--commit")

    assert _frozen_title(cert_a) == "NEW Title"
    assert _frozen_title(cert_b) == "NEW Title"
    assert "(2 certs)" in output


def test_placeholder_live_title_skips_program_without_writing():
    """A live title that is still the CMS placeholder is never stamped onto certs."""
    program, certificate = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="PLACEHOLDER - Some Program Certificate"
    )

    output = _run("--program", program.readable_id, "--commit")

    assert _frozen_title(certificate) == "OLD Title"
    assert "PLACEHOLDER" in output


def test_empty_live_title_skips_program_without_writing():
    """An empty live title is never stamped onto issued certificates."""
    program, certificate = _program_with_issued_cert(
        frozen_title="OLD Title", live_title="Temp Title"
    )
    # product_name is required at the CMS layer, so force the empty value at the
    # DB level (bypassing full_clean) to exercise the defensive guard.
    cert_page = program.page.certificate_page
    CertificatePage.objects.filter(pk=cert_page.pk).update(product_name="")

    _run("--program", program.readable_id, "--commit")

    assert _frozen_title(certificate) == "OLD Title"


def test_no_mode_flag_raises_command_error():
    """A bare run targets nothing: neither --program nor --all-programs errors."""
    with pytest.raises(CommandError):
        _run()


def test_both_mode_flags_raise_command_error():
    """--program and --all-programs are mutually exclusive."""
    with pytest.raises(CommandError):
        _run("--program", "program-v1:Org+Foo", "--all-programs")


def test_summary_line_reports_totals():
    """A final summary tallies programs processed, revisions changed, certs affected."""
    program, _ = _program_with_issued_cert("OLD Title", "NEW Title")

    output = _run("--program", program.readable_id, "--commit")

    assert "Summary" in output
    assert "1 program" in output
    assert "1 revision" in output
    assert "1 cert" in output


def test_unknown_program_is_reported_and_other_programs_still_processed():
    """A missing --program readable_id is reported and skipped, not fatal."""
    program, certificate = _program_with_issued_cert("OLD Title", "NEW Title")

    output = _run(
        "--program",
        "program-v1:Does+NotExist",
        "--program",
        program.readable_id,
        "--commit",
    )

    assert "Does+NotExist" in output
    assert _frozen_title(certificate) == "NEW Title"


def test_all_programs_processes_clean_programs_and_skips_placeholder():
    """--all-programs updates every clean program and skips placeholder ones."""
    _, clean_cert_a = _program_with_issued_cert("OLD A", "NEW A")
    _, clean_cert_b = _program_with_issued_cert("OLD B", "NEW B")
    _, placeholder_cert = _program_with_issued_cert(
        "OLD PH", "PLACEHOLDER - Foo Certificate"
    )

    _run("--all-programs", "--commit")

    assert _frozen_title(clean_cert_a) == "NEW A"
    assert _frozen_title(clean_cert_b) == "NEW B"
    assert _frozen_title(placeholder_cert) == "OLD PH"


def test_all_programs_skips_programs_without_cms_page():
    """--all-programs tolerates programs that have no CMS page / certificate page."""
    _, clean_cert = _program_with_issued_cert("OLD", "NEW")
    # A bare program with no CMS page at all (page is None).
    Program.objects.create(title="Bare", readable_id="program-v1:Bare+NoPage")

    _run("--all-programs", "--commit")  # must not raise

    assert _frozen_title(clean_cert) == "NEW"
