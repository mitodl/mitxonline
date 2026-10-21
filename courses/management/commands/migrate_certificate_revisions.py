"""
Management command to migrate every CourseRunCertificate/ProgramCertificate for
a course, course run, or program to the latest certificate page revision,
after asking for confirmation.

This is a targeted refresh tool for one course/run/program at a time (e.g.
after publishing a new certificate page revision that already-issued
certificates should pick up). Every certificate always has a revision
(certificate_page_revision is non-nullable since
courses/migrations/0112_certificate_page_revision_not_nullable.py, which
backfilled the ones that didn't), so this re-points existing certificates
rather than filling in missing ones.

Check the usages of this command below:

1. Update all certificates for a course
./manage.py migrate_certificate_revisions --course=<course_readable_id>

2. Update all certificates for a single course run
./manage.py migrate_certificate_revisions --courserun=<course_run_courseware_id>

3. Update all certificates for a program
./manage.py migrate_certificate_revisions --program=<program_readable_id>
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
        "Migrate every certificate of a course/course run/program to the latest "
        "certificate page revision, after asking for confirmation."
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

    def handle(self, *args, **options):  # noqa: ARG002
        """Handle command execution"""

        course_id = options.get("course")
        run_id = options.get("courserun")
        program_id = options.get("program")

        provided = [value for value in (course_id, run_id, program_id) if value]
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

        answer = input(
            self.style.WARNING(
                f"This will update all {certificates.count()} certificates for "
                f"{courseware_label} to revision {latest_revision.pk}. "
                "Continue? (y/n): "
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
