"""Backfill the frozen "Certificate Title" on already-issued program certificates."""

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from courses.models import Program, ProgramCertificate


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
        if bool(programs) == bool(all_programs):
            msg = (
                "Provide exactly one of --program <readable_id> (repeatable) "
                "or --all-programs."
            )
            raise CommandError(msg)

        commit = options["commit"]
        banner = "COMMIT" if commit else "DRY RUN"
        self.stdout.write(self.style.WARNING(f"=== {banner} ==="))

        programs_will_change = 0
        programs_already_correct = 0
        programs_skipped = 0
        revisions_changed = 0
        certs_affected = 0

        for readable_id, program in self._target_programs(programs, all_programs):
            if program is None:
                programs_skipped += 1
                self._write_block(
                    readable_id,
                    program_title="—",
                    new_title="—",
                    reason="no program with that readable_id",
                )
                continue

            certificate_page = self._certificate_page(program)
            if certificate_page is None:
                programs_skipped += 1
                self._write_block(
                    readable_id,
                    program_title=program.title,
                    new_title="—",
                    reason="no certificate page",
                )
                continue

            title = certificate_page.product_name

            if not title or title.startswith("PLACEHOLDER - "):
                programs_skipped += 1
                self._write_block(
                    readable_id,
                    program_title=program.title,
                    new_title=title or "—",
                    reason=(
                        f"live Certificate Title is empty or a placeholder "
                        f'("{title}") — fix the CMS page first'
                    ),
                )
                continue

            changed, n_revisions, n_certs = self._process_program(
                readable_id, program, title, commit=commit
            )
            revisions_changed += n_revisions
            certs_affected += n_certs
            if changed:
                programs_will_change += 1
            else:
                programs_already_correct += 1

        total = programs_will_change + programs_already_correct + programs_skipped
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {total} program(s), "
                f"{programs_will_change} will change, "
                f"{programs_already_correct} already correct, "
                f"{programs_skipped} skipped "
                f"({revisions_changed} revision(s), {certs_affected} cert(s) affected)."
            )
        )

    def _write_block(self, readable_id, *, program_title, new_title, reason):
        """Print a full per-program block for a program that is being skipped."""
        self.stdout.write("")
        self.stdout.write(readable_id)
        self.stdout.write(f"  Program Title    : {program_title}")
        self.stdout.write("  Cert Title (now) : —")
        self.stdout.write(f"  Cert Title (new) : {new_title}")
        self.stdout.write(
            self.style.WARNING(f"  Will change      : SKIPPED — {reason}")
        )

    def _process_program(self, readable_id, program, title, *, commit):
        """Print a valid program's block and (when committing) rewrite revisions.

        Returns ``(changed, revisions_changed, certs_affected)``.
        """
        # Build the block in memory and flush it only after the writes commit, so
        # a rollback never leaves behind output claiming a change that was undone.
        lines = [
            "",
            readable_id,
            f"  Program Title    : {program.title}",
            f"  Cert Title (new) : {title}",
        ]

        revisions = self._distinct_revisions(program)
        if not revisions:
            lines.append("  Cert Title (now) : —  (no issued certificates)")
            lines.append("  Will change      : NO")
            self._flush(lines)
            return False, 0, 0

        to_change = []
        revisions_changed = 0
        certs_affected = 0
        for revision, certs in revisions:
            old = revision.content.get("product_name")
            label = f"{len(certs)} cert(s), revision {revision.id}"
            lines.append(f"  Cert Title (now) : {old}  ({label})")
            if old == title:
                lines.append("  Will change      : NO")
                continue
            to_change.append(revision)
            revisions_changed += 1
            certs_affected += len(certs)
            lines.append(self.style.SUCCESS("  Will change      : YES"))

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
        """Yield ``(revision, certs)`` for each distinct non-null revision shared
        by the program's active certificates.
        """
        grouped = {}
        certs = ProgramCertificate.objects.filter(program=program).select_related(
            "certificate_page_revision"
        )
        for cert in certs:
            revision = cert.certificate_page_revision
            if revision is None:
                continue
            grouped.setdefault(revision.id, (revision, []))[1].append(cert)
        return list(grouped.values())
