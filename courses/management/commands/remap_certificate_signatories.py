"""Remap one signatory reference in issued certificates.

Issued certificates freeze their signatories into a Wagtail ``Revision`` as
SignatoryPage PK references. When a SignatoryPage is deleted, the frozen PK no
longer resolves and the signatory is silently dropped at render time (hq#12906).
This command rewrites the affected frozen revisions in place, swapping a single
``--old-id`` PK for a live ``--new-id``. Dry-run is the default; pass
``--commit`` to persist.

Examples
--------
    # Preview (14.100x): SignatoryPage 59 -> 788
    ./manage.py remap_certificate_signatories --old-id 59 --new-id 788

    # Apply it
    ./manage.py remap_certificate_signatories --old-id 59 --new-id 788 --commit

    # Restrict to a single course's certificates
    ./manage.py remap_certificate_signatories --old-id 59 --new-id 788 \
        --course course-v1:MITx+14.100x --commit

    # Test one frozen revision first (its id is shown in the dry-run report)
    ./manage.py remap_certificate_signatories --old-id 59 --new-id 788 \
        --revision-id 165 --commit
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from wagtail.models import Revision

from cms.models import SignatoryPage
from courses.models import (
    Course,
    CourseRunCertificate,
    Program,
    ProgramCertificate,
)

logger = logging.getLogger(__name__)

SIGNATORY_BLOCK_TYPE = "signatory"

LABEL_SIG_OLD = "Signatories (old)"
LABEL_SIG_NEW = "Signatories (new)"
LABEL_CHANGE_DRY = "Will change"
LABEL_CHANGE_COMMIT = "Changed"
LABEL_WIDTH = (
    max(map(len, (LABEL_SIG_OLD, LABEL_SIG_NEW, LABEL_CHANGE_DRY, LABEL_CHANGE_COMMIT)))
    + 2
)


def format_field(label, value):
    """Format one aligned ``  <label> : <value>`` report line."""
    return f"  {label:<{LABEL_WIDTH}}: {value}"


def get_content(revision):
    """Return ``revision.content`` as a dict (tolerating a raw JSON string)."""
    content = revision.content
    return content if isinstance(content, dict) else json.loads(content or "{}")


def get_signatory_blocks(content):
    """Return ``(blocks, is_json)`` for a revision's signatories stream.

    The nested StreamField value may be a JSON *string* or an already-decoded
    *list*; ``is_json`` records which so it can be written back in kind.
    """
    raw = content.get("signatories")
    is_json = isinstance(raw, str)
    if raw in (None, ""):
        return [], is_json
    return (json.loads(raw) if is_json else raw), is_json


def block_pk(block):
    """Return a signatory block's PK as an int, or ``None`` if unparseable."""
    try:
        return int(block.get("value"))
    except (TypeError, ValueError):
        return None


def signatory_pks(blocks):
    """Return the ordered signatory PKs referenced by ``blocks``."""
    return [
        block_pk(block) for block in blocks if block.get("type") == SIGNATORY_BLOCK_TYPE
    ]


def remap_blocks(blocks, old_id, new_id):
    """Swap ``old_id`` -> ``new_id`` across signatory blocks.

    No-op unless ``old_id`` is present. If the target is already a signatory
    (or ``old_id`` repeats), the duplicate block is dropped so the person is
    listed once. Block order and non-signatory keys are preserved. Returns
    ``(remapped_blocks, changed)``.
    """
    if old_id not in signatory_pks(blocks):
        return blocks, False

    seen = set()
    remapped = []
    for block in blocks:
        if block.get("type") != SIGNATORY_BLOCK_TYPE:
            remapped.append(block)
            continue
        current_pk = block_pk(block)
        target_pk = new_id if current_pk == old_id else current_pk
        if target_pk in seen:
            continue
        seen.add(target_pk)
        if target_pk == current_pk:
            remapped.append(block)
        else:
            # Write the new PK back in the same type as the block's stored value
            # (Wagtail stores ints, but match strings too for on-disk fidelity).
            new_value = (
                str(target_pk) if isinstance(block.get("value"), str) else target_pk
            )
            remapped.append({**block, "value": new_value})
    return remapped, True


@dataclass
class PlannedEdit:
    """A single frozen revision slated to have its signatories rewritten."""

    label: str
    revision: Revision
    cert_count: int
    content: dict
    signatories_is_json: bool
    remapped_blocks: list
    old_pks: list
    new_pks: list

    def serialized_signatories(self):
        """The new signatories value in the revision's original shape."""
        if self.signatories_is_json:
            return json.dumps(self.remapped_blocks)
        return self.remapped_blocks


class Command(BaseCommand):
    """Remap a single signatory PK in issued certificates' frozen revisions."""

    help = __doc__

    def add_arguments(self, parser):
        """Register the old/new signatory ids, optional scope, and --commit."""
        parser.add_argument(
            "--old-id",
            type=int,
            required=True,
            dest="old_id",
            help="Signatory PK currently frozen in the certificates (often deleted).",
        )
        parser.add_argument(
            "--new-id",
            type=int,
            required=True,
            dest="new_id",
            help="Replacement signatory PK to swap in (must be an existing SignatoryPage).",
        )
        parser.add_argument(
            "--course",
            dest="course",
            help="Restrict to one Course readable_id (course certificates only).",
        )
        parser.add_argument(
            "--program",
            dest="program",
            help="Restrict to one Program readable_id (program certificates only).",
        )
        parser.add_argument(
            "--revision-id",
            type=int,
            dest="revision_id",
            help="Restrict to a single frozen Revision id (e.g. for a controlled first run).",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Persist changes. Without this flag the command is a dry run.",
        )
        super().add_arguments(parser)

    def handle(self, *args, **options):  # noqa: ARG002
        """Remap ``old_id`` -> ``new_id`` in every affected frozen revision."""
        old_id = options["old_id"]
        new_id = options["new_id"]
        course_id = options.get("course")
        program_id = options.get("program")
        revision_id = options.get("revision_id")
        commit = options["commit"]

        if old_id == new_id:
            msg = "--old-id and --new-id must differ."
            raise CommandError(msg)
        if course_id and program_id:
            msg = "--course and --program are mutually exclusive."
            raise CommandError(msg)

        self.stdout.write(
            self.style.WARNING(f"=== {'COMMIT' if commit else 'DRY RUN'} ===")
        )

        new_page = SignatoryPage.objects.filter(pk=new_id).first()
        if new_page is None:
            # Refuse to stamp an unresolvable reference back onto certificates.
            self.stdout.write(
                self.style.ERROR(
                    f"SKIPPED — --new-id {new_id} does not resolve to a "
                    "SignatoryPage; no certificates were changed."
                )
            )
            self._write_summary(0, 0, commit=commit, skipped=[new_id])
            return

        self.stdout.write(
            f"Remapping signatory {old_id} -> {new_id} ({new_page.name!r})"
        )

        planned = self._plan_edits(old_id, new_id, course_id, program_id, revision_id)

        # Commit first, then report — so a rolled-back edit never leaves behind
        # output claiming success.
        if commit and planned:
            self._apply(planned)
        self._report(planned, commit=commit)

    def _plan_edits(self, old_id, new_id, course_id, program_id, revision_id):
        """Build the list of ``PlannedEdit``s for every affected frozen revision."""
        planned = []
        for label, revision, cert_count in self._distinct_revisions(
            course_id, program_id, revision_id
        ):
            content = get_content(revision)
            blocks, is_json = get_signatory_blocks(content)
            remapped_blocks, changed = remap_blocks(blocks, old_id, new_id)
            if not changed:
                continue
            planned.append(
                PlannedEdit(
                    label=label,
                    revision=revision,
                    cert_count=cert_count,
                    content=content,
                    signatories_is_json=is_json,
                    remapped_blocks=remapped_blocks,
                    old_pks=signatory_pks(blocks),
                    new_pks=signatory_pks(remapped_blocks),
                )
            )
        return planned

    @staticmethod
    def _apply(planned):
        """Persist all planned edits in a single atomic transaction."""
        with transaction.atomic():
            for edit in planned:
                edit.revision.content = {
                    **edit.content,
                    "signatories": edit.serialized_signatories(),
                }
                edit.revision.save(update_fields=["content"])
                # Durable audit trail beyond stdout for this data mutation.
                logger.info(
                    "remap_certificate_signatories: revision %s signatories "
                    "%s -> %s (%s cert(s))",
                    edit.revision.id,
                    edit.old_pks,
                    edit.new_pks,
                    edit.cert_count,
                )

    def _report(self, planned, *, commit):
        """Print a per-revision report and the final tally."""
        change_label = LABEL_CHANGE_COMMIT if commit else LABEL_CHANGE_DRY
        certs_affected = 0
        for edit in planned:
            certs_affected += edit.cert_count
            self.stdout.write("")
            self.stdout.write(f"{edit.label}  (rev {edit.revision.id})")
            self.stdout.write(
                format_field(
                    LABEL_SIG_OLD, f"{edit.old_pks}  ({edit.cert_count} cert(s))"
                )
            )
            self.stdout.write(format_field(LABEL_SIG_NEW, str(edit.new_pks)))
            self.stdout.write(self.style.SUCCESS(format_field(change_label, "YES")))
        self._write_summary(len(planned), certs_affected, commit=commit)

    def _write_summary(
        self, revisions_changed, certs_affected, *, commit, skipped=None
    ):
        """Print the final one-line tally."""
        change_word = "changed" if commit else "will change"
        skipped_note = f", skipped (unresolved --new-id): {skipped}" if skipped else ""
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {revisions_changed} revision(s) {change_word}, "
                f"{certs_affected} cert(s) affected{skipped_note}."
            )
        )

    def _distinct_revisions(self, course_id, program_id, revision_id):
        """Yield ``(label, revision, cert_count)`` per distinct frozen revision.

        Counts come from an indexed ``GROUP BY`` (no per-cert N+1); the revisions
        are then fetched in bulk. ``revision_id`` narrows to a single revision.
        """
        cert_counts = defaultdict(int)
        for queryset in self._target_querysets(course_id, program_id):
            certificates = queryset.filter(certificate_page_revision__isnull=False)
            if revision_id is not None:
                certificates = certificates.filter(
                    certificate_page_revision_id=revision_id
                )
            rows = certificates.values("certificate_page_revision_id").annotate(
                count=Count("id")
            )
            for row in rows:
                cert_counts[row["certificate_page_revision_id"]] += row["count"]

        revisions = Revision.objects.in_bulk(list(cert_counts))
        for rev_id, cert_count in cert_counts.items():
            revision = revisions.get(rev_id)
            if revision is not None:
                yield self._label_for(revision), revision, cert_count

    @staticmethod
    def _target_querysets(course_id, program_id):
        """Certificate querysets to scan for the requested scope.

        Uses ``all_objects`` so revoked certificates are fixed too; a revoked
        certificate can be reinstated and its frozen data still needs to be right.
        """
        if course_id:
            try:
                course = Course.objects.get(readable_id=course_id)
            except Course.DoesNotExist:
                msg = f"Could not find course with readable_id={course_id}."
                raise CommandError(msg)  # noqa: B904
            return [CourseRunCertificate.all_objects.filter(course_run__course=course)]
        if program_id:
            try:
                program = Program.objects.get(readable_id=program_id)
            except Program.DoesNotExist:
                msg = f"Could not find program with readable_id={program_id}."
                raise CommandError(msg)  # noqa: B904
            return [ProgramCertificate.all_objects.filter(program=program)]
        return [
            CourseRunCertificate.all_objects.all(),
            ProgramCertificate.all_objects.all(),
        ]

    @staticmethod
    def _label_for(revision):
        """Best-effort human label for a certificate page revision."""
        content = revision.content if isinstance(revision.content, dict) else {}
        return content.get("title") or f"certificate page {revision.object_id}"
