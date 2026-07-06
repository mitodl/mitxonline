"""Backfill the frozen "Certificate Title" on issued program certificates."""

from collections import Counter

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import Program, ProgramCertificate

# A live Certificate Title still carrying this prefix has never been filled in.
PLACEHOLDER_PREFIX = "PLACEHOLDER - "

# Report field labels. Kept as constants so the command and its tests stay in
# sync and the columns line up (the label column is padded to LABEL_WIDTH).
LABEL_WIDTH = 17
LABEL_PROGRAM_TITLE = "Program Title"
LABEL_CERT_OLD = "Cert Title (old)"
LABEL_CERT_NEW = "Cert Title (new)"
LABEL_CHANGE_DRY = "Will change"
LABEL_CHANGE_COMMIT = "Changed"


def format_field(label, value):
    """Format one aligned ``  <label> : <value>`` report line."""
    return f"  {label:<{LABEL_WIDTH}}: {value}"


class Command(BaseCommand):
    """Rewrite issued program certificates' frozen product_name to the live title."""

    help = __doc__

    def add_arguments(self, parser):
        """Add the command's program-selection and --commit arguments."""
        parser.add_argument("--program", action="append", dest="programs")
        parser.add_argument("--all-programs", action="store_true", dest="all_programs")
        parser.add_argument("--commit", action="store_true")
        super().add_arguments(parser)

    def handle(self, *args, **options):  # noqa: ARG002
        """Backfill frozen program-certificate titles from the live CMS page."""
        programs = options["programs"]
        all_programs = options["all_programs"]
        if not programs and not all_programs:
            msg = "Provide --program <readable_id> or --all-programs."
            raise CommandError(msg)
        if programs and all_programs:
            msg = "--program and --all-programs are mutually exclusive."
            raise CommandError(msg)

        commit = options["commit"]
        change_label = LABEL_CHANGE_COMMIT if commit else LABEL_CHANGE_DRY
        banner = "COMMIT" if commit else "DRY RUN"
        self.stdout.write(self.style.WARNING(f"=== {banner} ==="))

        tally = Counter()

        for readable_id, program in self._target_programs(programs, all_programs):
            if program is None:
                tally["skipped"] += 1
                self._write_block(
                    readable_id,
                    change_label=change_label,
                    program_title="—",
                    new_title="—",
                    reason="no program with that readable_id",
                )
                continue

            certificate_page = self._certificate_page(program)
            if certificate_page is None:
                tally["skipped"] += 1
                self._write_block(
                    readable_id,
                    change_label=change_label,
                    program_title=program.title,
                    new_title="—",
                    reason="no certificate page",
                )
                continue

            title = certificate_page.product_name

            if not title or title.startswith(PLACEHOLDER_PREFIX):
                tally["skipped"] += 1
                self._write_block(
                    readable_id,
                    change_label=change_label,
                    program_title=program.title,
                    new_title=title or "—",
                    reason=(
                        f"live Certificate Title is empty or a placeholder "
                        f'("{title}") — fix the CMS page first'
                    ),
                )
                continue

            changed, n_revisions, n_certs = self._process_program(
                readable_id, program, title, commit=commit, change_label=change_label
            )
            tally["revisions"] += n_revisions
            tally["certs"] += n_certs
            tally["will_change" if changed else "already_correct"] += 1

        total = tally["will_change"] + tally["already_correct"] + tally["skipped"]
        change_word = "changed" if commit else "will change"
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {total} program(s), "
                f"{tally['will_change']} {change_word}, "
                f"{tally['already_correct']} already correct, "
                f"{tally['skipped']} skipped "
                f"({tally['revisions']} revision(s), "
                f"{tally['certs']} cert(s) affected)."
            )
        )

    def _write_block(
        self, readable_id, *, change_label, program_title, new_title, reason
    ):
        """Print a full per-program block for a program that is being skipped."""
        self.stdout.write("")
        self.stdout.write(readable_id)
        self.stdout.write(format_field(LABEL_PROGRAM_TITLE, program_title))
        self.stdout.write(format_field(LABEL_CERT_OLD, "—"))
        self.stdout.write(format_field(LABEL_CERT_NEW, new_title))
        self.stdout.write(
            self.style.WARNING(format_field(change_label, f"SKIPPED — {reason}"))
        )

    def _process_program(self, readable_id, program, title, *, commit, change_label):
        """Print a valid program's block and (when committing) rewrite revisions.

        Returns ``(changed, revisions_changed, certs_affected)``.
        """
        # Build the block in memory and flush it only after the writes commit, so
        # a rollback never leaves behind output claiming a change that was undone.
        lines = [
            "",
            readable_id,
            format_field(LABEL_PROGRAM_TITLE, program.title),
            format_field(LABEL_CERT_NEW, title),
        ]

        revisions = self._distinct_revisions(program)
        if not revisions:
            lines.append(format_field(LABEL_CERT_OLD, "—  (no issued certificates)"))
            lines.append(format_field(change_label, "NO"))
            self._flush(lines)
            return False, 0, 0

        to_change = []
        revisions_changed = 0
        certs_affected = 0
        for revision, certs in revisions:
            old = revision.content.get("product_name")
            count = f"{len(certs)} cert(s), revision {revision.id}"
            lines.append(format_field(LABEL_CERT_OLD, f"{old}  ({count})"))
            if old == title:
                lines.append(format_field(change_label, "NO"))
                continue
            to_change.append(revision)
            revisions_changed += 1
            certs_affected += len(certs)
            lines.append(self.style.SUCCESS(format_field(change_label, "YES")))

        if commit and to_change:
            with transaction.atomic():
                for revision in to_change:
                    # Build a fresh dict rather than mutating revision.content in
                    # place, so the stored JSONField is replaced cleanly.
                    revision.content = {**revision.content, "product_name": title}
                    revision.save(update_fields=["content"])

        self._flush(lines)
        return bool(to_change), revisions_changed, certs_affected

    def _flush(self, lines):
        """Write the collected report lines for one program to stdout."""
        for line in lines:
            self.stdout.write(line)

    @staticmethod
    def _target_programs(programs, all_programs):
        """Yield ``(readable_id, program_or_None)`` for each targeted program.

        For ``--program`` a missing readable_id yields ``(readable_id, None)`` so
        the caller can report and skip it. For ``--all-programs`` every program is
        yielded (with its own readable_id).
        """
        if all_programs:
            for program in Program.objects.all().order_by("readable_id"):
                yield program.readable_id, program
            return
        by_readable_id = {
            program.readable_id: program
            for program in Program.objects.filter(readable_id__in=programs)
        }
        for readable_id in programs:
            yield readable_id, by_readable_id.get(readable_id)

    @staticmethod
    def _certificate_page(program):
        """Return the program's live ``CertificatePage``, or ``None`` if the
        program has no CMS page or no certificate page.
        """
        try:
            page = program.page
        except ObjectDoesNotExist:
            return None
        if page is None:
            return None
        return page.certificate_page

    @staticmethod
    def _distinct_revisions(program):
        """Return ``[(revision, certs), ...]`` for each distinct non-null revision
        shared by the program's certificates.

        Uses ``all_objects`` so revoked (and any future-dated) certificates are
        included — their frozen titles need backfilling too.
        """
        grouped = {}
        certs = ProgramCertificate.all_objects.filter(program=program).select_related(
            "certificate_page_revision"
        )
        for cert in certs:
            revision = cert.certificate_page_revision
            if revision is None:
                continue
            grouped.setdefault(revision.id, (revision, []))[1].append(cert)
        return list(grouped.values())
