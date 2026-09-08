"""Tests for the remap_certificate_signatories management command."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from wagtail.blocks import StreamValue
from wagtail.models import Revision

from cms.factories import (
    CoursePageFactory,
    ProgramPageFactory,
    SignatoryPageFactory,
)
from courses.factories import (
    CourseRunCertificateFactory,
    CourseRunFactory,
    ProgramCertificateFactory,
)
from courses.management.commands.remap_certificate_signatories import (
    LABEL_CHANGE_COMMIT,
    LABEL_CHANGE_DRY,
    LABEL_SIG_NEW,
    LABEL_SIG_OLD,
    format_field,
)
from courses.models import CourseRunCertificate

pytestmark = [pytest.mark.django_db]

COMMAND = "remap_certificate_signatories"


def _run(*args):
    """Invoke the command, returning captured stdout."""
    out, err = StringIO(), StringIO()
    call_command(COMMAND, *args, stdout=out, stderr=err)
    return out.getvalue()


def _freeze_signatories(cert_page, signatory_pages):
    """Set ``cert_page``'s signatories to ``signatory_pages`` and freeze a revision.

    Returns the frozen ``Revision``.
    """
    cert_page.signatories = StreamValue(
        cert_page.signatories.stream_block,
        [("signatory", page) for page in signatory_pages],
        is_lazy=False,
    )
    cert_page.save()
    return cert_page.save_revision()


def _course_cert(signatory_pages, *, course_run=None):
    """Create a course certificate frozen against a revision that references
    ``signatory_pages``. Returns ``(course_page, certificate, revision)``.
    """
    course_page = CoursePageFactory.create()
    revision = _freeze_signatories(course_page.certificate_page, signatory_pages)
    kwargs = {"certificate_page_revision": revision}
    if course_run is not None:
        kwargs["course_run"] = course_run
    certificate = CourseRunCertificateFactory.create(**kwargs)
    return course_page, certificate, revision


def _frozen_sig_pks(revision):
    """Return the signatory PKs frozen in a revision (shape-agnostic)."""
    revision.refresh_from_db()
    content = (
        revision.content
        if isinstance(revision.content, dict)
        else json.loads(revision.content)
    )
    sig = content.get("signatories")
    blocks = json.loads(sig) if isinstance(sig, str) else sig
    return [block["value"] for block in blocks]


def test_commit_swaps_old_for_new_in_frozen_content():
    """--commit rewrites the frozen signatory reference old_id -> new_id."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, other])

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [new.id, other.id]


def test_dry_run_by_default_makes_no_changes():
    """Without --commit the command reports but never writes to the DB."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, other])

    _run("--old-id", str(old.id), "--new-id", str(new.id))

    assert _frozen_sig_pks(revision) == [old.id, other.id]


def test_dry_run_output_reports_planned_change():
    """Dry-run output shows the old and new signatory lists and a YES flag."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _course_cert([old, other])

    output = _run("--old-id", str(old.id), "--new-id", str(new.id))

    assert "DRY RUN" in output
    assert format_field(LABEL_SIG_OLD, f"{[old.id, other.id]}  (1 cert(s))") in output
    assert format_field(LABEL_SIG_NEW, str([new.id, other.id])) in output
    assert format_field(LABEL_CHANGE_DRY, "YES") in output


def test_commit_is_idempotent():
    """A second --commit run is a no-op: nothing left to change."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, other])

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")
    output = _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [new.id, other.id]
    assert "0 revision(s)" in output
    assert format_field(LABEL_CHANGE_COMMIT, "YES") not in output


def test_shared_revision_updated_once_for_all_certs():
    """Certs sharing one revision are all fixed by a single edit; certs counted."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    course_page = CoursePageFactory.create()
    revision = _freeze_signatories(course_page.certificate_page, [old, other])
    CourseRunCertificateFactory.create(certificate_page_revision=revision)
    CourseRunCertificateFactory.create(certificate_page_revision=revision)

    output = _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [new.id, other.id]
    assert "2 cert(s)" in output


def test_revoked_certificate_is_also_remapped():
    """Revoked certs are included (all_objects): their frozen refs are fixed too."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, certificate, revision = _course_cert([old, other])
    CourseRunCertificate.all_objects.filter(pk=certificate.pk).update(is_revoked=True)

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [new.id, other.id]


def test_duplicate_target_is_dropped_not_duplicated():
    """When the new id is already present, the remapped block is de-duplicated."""
    old, new, other = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, new, other])

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [new.id, other.id]


def test_json_string_shape_is_preserved():
    """A revision whose signatories is a JSON *string* stays a string after edit."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, other])
    content = (
        revision.content
        if isinstance(revision.content, dict)
        else json.loads(revision.content)
    )
    if not isinstance(content["signatories"], str):
        content["signatories"] = json.dumps(content["signatories"])
        revision.content = content
        revision.save(update_fields=["content"])

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    revision.refresh_from_db()
    assert isinstance(revision.content["signatories"], str)
    assert _frozen_sig_pks(revision) == [new.id, other.id]


def test_string_pk_values_are_written_back_as_strings():
    """If a revision stores signatory PKs as strings, the swapped-in PK is
    written back as a string too, so the stream stays a single type.
    """
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, other])
    content = (
        revision.content
        if isinstance(revision.content, dict)
        else json.loads(revision.content)
    )
    raw = content["signatories"]
    is_json = isinstance(raw, str)
    blocks = json.loads(raw) if is_json else raw
    for block in blocks:
        block["value"] = str(block["value"])
    content["signatories"] = json.dumps(blocks) if is_json else blocks
    revision.content = content
    revision.save(update_fields=["content"])

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [str(new.id), str(other.id)]


def test_list_shape_is_preserved():
    """A revision whose signatories is a *list* stays a list after edit."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, revision = _course_cert([old, other])
    content = (
        revision.content
        if isinstance(revision.content, dict)
        else json.loads(revision.content)
    )
    if isinstance(content["signatories"], str):
        content["signatories"] = json.loads(content["signatories"])
        revision.content = content
        revision.save(update_fields=["content"])

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    revision.refresh_from_db()
    assert isinstance(revision.content["signatories"], list)
    assert _frozen_sig_pks(revision) == [new.id, other.id]


def test_missing_new_id_makes_no_changes_and_is_reported():
    """An unresolved --new-id is reported and skipped; nothing is written."""
    old, other = SignatoryPageFactory.create_batch(2)
    _, _, revision = _course_cert([old, other])
    missing_id = 9_999_999

    output = _run("--old-id", str(old.id), "--new-id", str(missing_id), "--commit")

    assert _frozen_sig_pks(revision) == [old.id, other.id]
    assert "SKIPPED" in output
    assert str(missing_id) in output


def test_null_revision_cert_is_skipped_without_error():
    """A certificate with no frozen revision is ignored, not an error."""
    new = SignatoryPageFactory.create()
    certificate = CourseRunCertificateFactory.create(certificate_page_revision=None)

    _run("--old-id", "1", "--new-id", str(new.id), "--commit")

    certificate.refresh_from_db()
    assert certificate.certificate_page_revision is None


def test_program_certificate_is_remapped():
    """Program certificates are covered as well as course certificates."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    program_page = ProgramPageFactory.create()
    revision = _freeze_signatories(program_page.certificate_page, [old, other])
    ProgramCertificateFactory.create(
        program=program_page.program, certificate_page_revision=revision
    )

    _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(revision) == [new.id, other.id]


def test_program_scope_limits_to_that_program():
    """--program only touches revisions of that program's certificates."""
    old, other, new = SignatoryPageFactory.create_batch(3)

    scoped_page = ProgramPageFactory.create()
    scoped_rev = _freeze_signatories(scoped_page.certificate_page, [old, other])
    ProgramCertificateFactory.create(
        program=scoped_page.program, certificate_page_revision=scoped_rev
    )

    other_page = ProgramPageFactory.create()
    other_rev = _freeze_signatories(other_page.certificate_page, [old, other])
    ProgramCertificateFactory.create(
        program=other_page.program, certificate_page_revision=other_rev
    )

    _run(
        "--old-id",
        str(old.id),
        "--new-id",
        str(new.id),
        "--program",
        scoped_page.program.readable_id,
        "--commit",
    )

    assert _frozen_sig_pks(scoped_rev) == [new.id, other.id]
    assert _frozen_sig_pks(other_rev) == [old.id, other.id]


def test_unscoped_run_covers_both_course_and_program_certs():
    """With no scope, a single run fixes course AND program certificates."""
    old, other, new = SignatoryPageFactory.create_batch(3)

    _, _, course_rev = _course_cert([old, other])

    program_page = ProgramPageFactory.create()
    program_rev = _freeze_signatories(program_page.certificate_page, [old, other])
    ProgramCertificateFactory.create(
        program=program_page.program, certificate_page_revision=program_rev
    )

    output = _run("--old-id", str(old.id), "--new-id", str(new.id), "--commit")

    assert _frozen_sig_pks(course_rev) == [new.id, other.id]
    assert _frozen_sig_pks(program_rev) == [new.id, other.id]
    assert "2 revision(s)" in output


def test_course_scope_limits_to_that_course():
    """--course only touches revisions of that course's certificates."""
    old, other, new = SignatoryPageFactory.create_batch(3)

    scoped_page = CoursePageFactory.create()
    scoped_rev = _freeze_signatories(scoped_page.certificate_page, [old, other])
    scoped_run = CourseRunFactory.create(course=scoped_page.course)
    CourseRunCertificateFactory.create(
        course_run=scoped_run, certificate_page_revision=scoped_rev
    )

    _, _, other_rev = _course_cert([old, other])

    _run(
        "--old-id",
        str(old.id),
        "--new-id",
        str(new.id),
        "--course",
        scoped_page.course.readable_id,
        "--commit",
    )

    assert _frozen_sig_pks(scoped_rev) == [new.id, other.id]
    assert _frozen_sig_pks(other_rev) == [old.id, other.id]


def test_revision_id_limits_to_that_revision():
    """--revision-id only touches the one frozen revision, not its siblings."""
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, target_rev = _course_cert([old, other])
    _, _, bystander_rev = _course_cert([old, other])

    output = _run(
        "--old-id",
        str(old.id),
        "--new-id",
        str(new.id),
        "--revision-id",
        str(target_rev.id),
        "--commit",
    )

    assert _frozen_sig_pks(target_rev) == [new.id, other.id]
    assert _frozen_sig_pks(bystander_rev) == [old.id, other.id]
    assert "1 revision(s)" in output


def test_old_equals_new_raises_command_error():
    """--old-id and --new-id must differ."""
    new = SignatoryPageFactory.create()
    with pytest.raises(CommandError):
        _run("--old-id", str(new.id), "--new-id", str(new.id))


def test_course_and_program_are_mutually_exclusive():
    """--course and --program cannot both be given."""
    new = SignatoryPageFactory.create()
    with pytest.raises(CommandError):
        _run(
            "--old-id",
            "1",
            "--new-id",
            str(new.id),
            "--course",
            "course-v1:MITx+Foo",
            "--program",
            "program-v1:MITx+Bar",
        )


def test_unknown_course_raises_command_error():
    """A missing --course readable_id is a hard error."""
    new = SignatoryPageFactory.create()
    with pytest.raises(CommandError):
        _run(
            "--old-id",
            "1",
            "--new-id",
            str(new.id),
            "--course",
            "course-v1:Does+NotExist",
        )


def test_commit_rollback_emits_no_misleading_success_output(mocker):
    """If a revision save fails mid-commit, the atomic block rolls everything
    back and no output claims a change succeeded (report flushed post-commit).
    """
    old, other, new = SignatoryPageFactory.create_batch(3)
    _, _, rev_a = _course_cert([old, other])
    _, _, rev_b = _course_cert([old, other])

    original_save = Revision.save
    state = {"calls": 0}

    def flaky_save(self, *args, **kwargs):
        state["calls"] += 1
        if state["calls"] >= 2:
            msg = "simulated DB failure"
            raise DatabaseError(msg)
        return original_save(self, *args, **kwargs)

    mocker.patch.object(Revision, "save", autospec=True, side_effect=flaky_save)

    out = StringIO()
    with pytest.raises(DatabaseError):
        call_command(
            COMMAND,
            "--old-id",
            str(old.id),
            "--new-id",
            str(new.id),
            "--commit",
            stdout=out,
        )

    output = out.getvalue()
    assert format_field(LABEL_CHANGE_COMMIT, "YES") not in output
    assert _frozen_sig_pks(rev_a) == [old.id, other.id]
    assert _frozen_sig_pks(rev_b) == [old.id, other.id]
