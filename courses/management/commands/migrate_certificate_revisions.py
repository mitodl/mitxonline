"""
Management command to migrate CourseRunCertificates/ProgramCertificates for a
course, course run, or program to the latest certificate page revision.

By default, only certificates that don't have a certificate_page_revision
associated are updated. Pass --all to update every certificate for the
course/run/program, even ones that already have a revision set.

Check the usages of this command below:

1. Update certificates with no revision associated, for a course
./manage.py migrate_certificate_revisions --course=<course_readable_id>

2. Update ALL certificates (including ones that already have a revision), for a course
./manage.py migrate_certificate_revisions --course=<course_readable_id> --all

3. Same operations, but for a single course run
./manage.py migrate_certificate_revisions --courserun=<course_run_courseware_id>
./manage.py migrate_certificate_revisions --courserun=<course_run_courseware_id> --all

4. Same operations, but for a program
./manage.py migrate_certificate_revisions --program=<program_readable_id>
./manage.py migrate_certificate_revisions --program=<program_readable_id> --all

5. Update certificates with no revision associated, across every course and
   program that has a live certificate page (used to backfill in bulk before
   making certificate_page_revision non-nullable). Courses/programs whose
   certificate page has no revision to backfill from are reported and
   skipped rather than failing the whole run - use
   report_certificates_missing_revision afterwards to see what's left.
./manage.py migrate_certificate_revisions --all-missing
"""

from django.core.management.base import BaseCommand, CommandError

from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    Program,
    ProgramCertificate,
)


class Command(BaseCommand):
    """
    Invoke with:

        python manage.py migrate_certificate_revisions
    """

    help = (
        "Migrate certificates of a course/course run/program to the latest "
        "certificate page revision. By default only certificates with no revision "
        "associated are updated; use --all to update every certificate for the "
        "course/run/program; use --all-missing to backfill missing revisions "
        "across every course and program at once."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--course", type=str, help="The 'readable_id' value for a Course"
        )
        parser.add_argument(
            "--courserun", type=str, help="The 'courseware_id' value for a CourseRun"
        )
        parser.add_argument(
            "--program", type=str, help="The 'readable_id' value for a Program"
        )
        parser.add_argument(
            "--all",
            dest="update_all",
            action="store_true",
            required=False,
            help=(
                "Update all certificates for the course/run/program to the latest "
                "revision. By default, only certificates with no revision "
                "associated are updated."
            ),
        )
        parser.add_argument(
            "--all-missing",
            dest="all_missing",
            action="store_true",
            required=False,
            help=(
                "Backfill certificate_page_revision for every certificate that's "
                "missing one, across every course and program with a live "
                "certificate page. Cannot be combined with --course/--courserun/"
                "--program/--all."
            ),
        )

        super().add_arguments(parser)

    def _resolve_certificate_scope(self, course_id, run_id, program_id):
        """Resolve the certificate page, label, and certificate queryset for the target"""
        if course_id:
            try:
                course = Course.objects.get(readable_id=course_id)
            except Course.DoesNotExist:
                message = f"Could not find course with readable_id={course_id}."
                raise CommandError(message)  # noqa: B904

            return (
                course.certificate_page,
                f"course {course.readable_id}",
                CourseRunCertificate.all_objects.filter(course_run__course=course),
            )

        if run_id:
            try:
                course_run = CourseRun.objects.get(courseware_id=run_id)
            except CourseRun.DoesNotExist:
                message = f"Could not find course run with courseware_id={run_id}."
                raise CommandError(message)  # noqa: B904

            return (
                course_run.course.certificate_page,
                f"course run {course_run.courseware_id}",
                CourseRunCertificate.all_objects.filter(course_run=course_run),
            )

        try:
            program = Program.objects.get(readable_id=program_id)
        except Program.DoesNotExist:
            message = f"Could not find program with readable_id={program_id}."
            raise CommandError(message)  # noqa: B904

        return (
            program.certificate_page,
            f"program {program.readable_id}",
            ProgramCertificate.all_objects.filter(program=program),
        )

    def _backfill_all_missing(self):
        """
        Backfill certificate_page_revision, across every course and program
        with a live certificate page, for certificates that don't have one.

        Courses/programs whose certificate page has no revision to backfill
        from are reported and skipped rather than aborting the whole run -
        those need a human to fix the CertificatePage first (see
        report_certificates_missing_revision).
        """
        total_updated = 0

        for course in Course.objects.all():
            certificate_page = course.certificate_page
            if not certificate_page:
                continue

            latest_revision = certificate_page.get_latest_revision()
            if not latest_revision:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping course {course.readable_id}: certificate page "
                        f"'{certificate_page.title}' (id={certificate_page.pk}) has "
                        "no revisions."
                    )
                )
                continue

            updated_count = CourseRunCertificate.all_objects.filter(
                course_run__course=course, certificate_page_revision__isnull=True
            ).update(certificate_page_revision=latest_revision)

            if updated_count:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated {updated_count} certificate(s) for course "
                        f"{course.readable_id} to revision {latest_revision.pk}."
                    )
                )
            total_updated += updated_count

        for program in Program.objects.all():
            certificate_page = program.certificate_page
            if not certificate_page:
                continue

            latest_revision = certificate_page.get_latest_revision()
            if not latest_revision:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping program {program.readable_id}: certificate page "
                        f"'{certificate_page.title}' (id={certificate_page.pk}) has "
                        "no revisions."
                    )
                )
                continue

            updated_count = ProgramCertificate.all_objects.filter(
                program=program, certificate_page_revision__isnull=True
            ).update(certificate_page_revision=latest_revision)

            if updated_count:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated {updated_count} certificate(s) for program "
                        f"{program.readable_id} to revision {latest_revision.pk}."
                    )
                )
            total_updated += updated_count

        self.stdout.write(
            self.style.SUCCESS(f"Updated {total_updated} certificate(s) in total.")
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""

        course_id = options.get("course")
        run_id = options.get("courserun")
        program_id = options.get("program")
        update_all = options.get("update_all")
        all_missing = options.get("all_missing")

        provided = [value for value in (course_id, run_id, program_id) if value]

        if all_missing:
            if provided or update_all:
                message = (
                    "--all-missing cannot be combined with --course, --courserun, "
                    "--program, or --all."
                )
                raise CommandError(message)
            self._backfill_all_missing()
            return

        if not provided:
            message = "The command needs one of --course, --courserun, or --program."
            raise CommandError(message)

        if len(provided) > 1:
            message = "Provide only one of --course, --courserun, or --program."
            raise CommandError(message)

        certificate_page, courseware_label, certificates = (
            self._resolve_certificate_scope(course_id, run_id, program_id)
        )

        if not certificate_page:
            message = f"No certificate page found for {courseware_label}."
            raise CommandError(message)

        latest_revision = certificate_page.get_latest_revision()
        if not latest_revision:
            message = f"Certificate page '{certificate_page.title}' (id={certificate_page.pk}) for {courseware_label} has no revisions."
            raise CommandError(message)

        if not update_all:
            certificates = certificates.filter(certificate_page_revision__isnull=True)
        else:
            answer = input(
                self.style.WARNING(
                    f"This will update {len(certificates)} certificates for {courseware_label} to "
                    f"revision {latest_revision.pk}, including ones that already "
                    "have a revision set. Continue? (y/n): "
                )
            ).lower()
            if answer != "y":
                self.stdout.write(self.style.WARNING("Aborted. No changes made."))
                return

        updated_count = certificates.update(certificate_page_revision=latest_revision)

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated_count} certificate(s) for {courseware_label} to "
                f"revision {latest_revision.pk}."
            )
        )
