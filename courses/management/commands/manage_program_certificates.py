"""
Management command to revoke, un revoke or create a certificate for a program for the given User.

Check the usages of this command below:

**Program Certificate Creation**

1. Generate Program certificate for a user
./manage.py manage_program_certificates —-create -—program=<program_readable_id> -—user=<username or email>

2. Forcefully Generate Program certificate for a user use -f or --force
./manage.py manage_program_certificates —-create -—program=<program_readable_id> -—user=<username or email> -f

**Revoke/Un-revoke Program Certificates**

3. Revoke a program certificate for a user
./mange.py manage_program_certificates -—revoke -—user=<username or email> -—program=<program_readable_id>

4. Un-Revoke a program certificate for a user
./mange.py manage_program_certificates -—unrevoke —-program=<program_readable_id> -—user=<username or email>

5. Generate Program certificate for all enrolled users in the program who have earned it
./mange.py manage_program_certificates --create -—program=<program_readable_id>

When a certificate isn't created, the command says why. If the program's
requirements aren't met, it lists each requirement and why it isn't met. In
bulk mode (no --user) it prints a count per reason; pass -v 2 to list each
skipped user with the requirements they're missing, or -v 3 for each skipped
user's full requirement breakdown.
"""

from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from courses.api import (
    ProgramCertificateSkipReason,
    explain_program_requirements,
    generate_program_certificate_with_result,
    manage_program_certificate_access,
)
from courses.models import Program, ProgramEnrollment
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """
    Invoke with:

        python manage.py manage_program_certificates
    """

    help = "Revoke, un revoke or create a program certificate for a program for the given User"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email or username of the enrolled User",
            required=False,
        )
        parser.add_argument(
            "--program",
            type=str,
            help="The id, email or username of the enrolled User",
            required=True,
        )
        parser.add_argument(
            "--revoke", dest="revoke", action="store_true", required=False
        )
        parser.add_argument(
            "--unrevoke", dest="unrevoke", action="store_true", required=False
        )
        parser.add_argument(
            "--create", dest="create", action="store_true", required=False
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            dest="force",
            help=(
                "If provided, the certificate will be generated even if all required "
                "courses for the program are not passed"
            ),
        )

        super().add_arguments(parser)

    def handle(self, *args, **options):  # pylint: disable=too-many-locals  # noqa: ARG002
        """Handle command execution"""

        revoke = options.get("revoke")
        unrevoke = options.get("unrevoke")
        create = options.get("create")
        program = options.get("program")
        user = options.get("user")
        force_create = options.get("force", False)

        if not (revoke or unrevoke) and not create:
            raise CommandError(
                "The command needs a valid action e.g. --revoke, --unrevoke, --create."  # noqa: EM101
            )

        if user:
            try:
                user = fetch_user(user)
            except User.DoesNotExist:
                raise CommandError(  # noqa: B904
                    f"Could not find a user with <username or email>={user}."  # noqa: EM102
                )

        # Unable to obtain a program object based on the provided program readable id
        try:
            program = Program.objects.get(readable_id=program)
        except Program.DoesNotExist:
            raise CommandError(f"Could not find program with readable_id={program}.")  # noqa: B904, EM102

        # Handle revoke/un-revoke of a certificate
        if revoke or unrevoke:
            if not user:
                raise CommandError(
                    "If you want to revoke/unrevoke a user argument is required"  # noqa: EM101
                )
            revoke_status = manage_program_certificate_access(
                user=user,
                program=program,
                revoke_state=True if revoke else False,  # noqa: SIM210
            )

            if revoke_status:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Certificate for {} has been {}".format(
                            f"program: {program}",
                            "revoked." if revoke else "un-revoked.",
                        )
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("No changes made."))

        # Handle the creation of the program certificate.
        elif create:
            verbosity = options.get("verbosity", 1)
            if user:
                self._create_for_user(user, program, force_create=force_create)
            else:
                self._create_for_enrollments(program, verbosity=verbosity)

    def _requirement_lines(self, user, program, *, unmet_only):
        """Lines describing the user's standing against the program's requirements."""
        result = explain_program_requirements(user, program)
        if result is None:
            return ["The program has no requirements set up."]
        if unmet_only:
            leaves = result.unmet_leaves()
            if not leaves:
                return []
            return [
                f"  Missing: {leaf.label}"
                + (f" ({leaf.detail})" if leaf.detail else "")
                for leaf in leaves
            ]
        return [f"  {line}" for line in result.format_lines()]

    def _create_for_user(self, user, program, *, force_create):
        result = generate_program_certificate_with_result(
            user=user, program=program, force_create=force_create
        )
        prefix = (
            f"Processed user {user.edx_username} ({user.email}) in program "
            f"{program.readable_id}. Result - Certificate: "
        )
        if result.created:
            self.stdout.write(self.style.SUCCESS(f"{prefix}created"))
            return
        if result.certificate is not None:
            self.stdout.write(self.style.SUCCESS(f"{prefix}already exists"))
            return

        message = f"{prefix}not created, {result.skip_reason}."
        if result.skip_reason == ProgramCertificateSkipReason.REQUIREMENTS_NOT_MET:
            message += (
                " Use -f or --force to create the certificate anyway.\nRequirements:"
            )
        elif result.skip_reason == ProgramCertificateSkipReason.NO_ACTIVE_ENROLLMENT:
            message += " Use -f or --force to create the certificate anyway."
        self.stdout.write(self.style.ERROR(message))
        if result.skip_reason == ProgramCertificateSkipReason.REQUIREMENTS_NOT_MET:
            for line in self._requirement_lines(user, program, unmet_only=False):
                self.stdout.write(line)

    def _create_for_enrollments(self, program, *, verbosity):
        """Generate certificates for all enrolled users, reporting who was skipped and why."""
        enrollments = ProgramEnrollment.objects.filter(program=program).select_related(
            "user"
        )
        created_count = 0
        existing_count = 0
        skipped = Counter()
        for enrollment in enrollments:
            result = generate_program_certificate_with_result(
                user=enrollment.user, program=program
            )
            if result.created:
                created_count += 1
                continue
            if result.certificate is not None:
                existing_count += 1
                continue

            skipped[result.skip_reason] += 1
            if verbosity >= 2:  # noqa: PLR2004
                learner = enrollment.user
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped {learner.edx_username} ({learner.email}): "
                        f"{result.skip_reason}"
                    )
                )
                if (
                    result.skip_reason
                    == ProgramCertificateSkipReason.REQUIREMENTS_NOT_MET
                ):
                    for line in self._requirement_lines(
                        learner,
                        program,
                        unmet_only=verbosity < 3,  # noqa: PLR2004
                    ):
                        self.stdout.write(line)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {created_count} certificates for program "
                f"{program.readable_id}"
            )
        )
        if existing_count:
            self.stdout.write(f"{existing_count} enrolled user(s) already had one.")
        for reason, count in skipped.most_common():
            self.stdout.write(self.style.WARNING(f"Skipped {count} user(s): {reason}."))
        if skipped and verbosity < 2:  # noqa: PLR2004
            self.stdout.write(
                "Run with -v 2 to list each skipped user and what they're missing."
            )
