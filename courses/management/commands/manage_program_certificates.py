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

"""

from django.core.management.base import BaseCommand, CommandError
from users.api import fetch_user
from courses.api import manage_program_certificate_access, generate_program_certificate
from courses.models import Program
from django.contrib.auth import get_user_model

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
            required=True,
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

    def handle(self, *args, **options):  # pylint: disable=too-many-locals
        """Handle command execution"""

        revoke = options.get("revoke")
        unrevoke = options.get("unrevoke")
        create = options.get("create")
        program = options.get("program")
        user = options.get("user")
        force_create = options.get("force", False)

        if not (revoke or unrevoke) and not create and not user:
            raise CommandError(
                "The command needs a valid action e.g. --revoke, --unrevoke, --create."
            )

        try:
            user = fetch_user(user)
        except User.DoesNotExist:
            raise CommandError(
                "Could not find a user with <username or email>={}.".format(user)
            )

        # Unable to obtain a program object based on the provided program readable id
        try:
            program = Program.objects.get(readable_id=program)
        except Program.DoesNotExist:
            raise CommandError(
                "Could not find program with readable_id={}.".format(program)
            )

        # Handle revoke/un-revoke of a certificate
        if revoke or unrevoke:
            revoke_status = manage_program_certificate_access(
                user=user,
                program=program,
                revoke_state=True if revoke else False,
            )

            if revoke_status:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Certificate for {} has been {}".format(
                            "program: {}".format(program),
                            "revoked." if revoke else "un-revoked.",
                        )
                    )
                )
            else:
                self.stdout.write(self.style.WARNING("No changes made."))

        # Handle the creation of the program certificate.
        elif create:

            # If -f or --force argument is provided, we'll forcefully generate the program certificate
            certificate, created_cert = generate_program_certificate(
                user=user, program=program, force_create=force_create
            )
            success_result = True

            if created_cert:
                cert_status = "created"
            elif certificate and not created_cert:
                cert_status = "already exists"
            else:
                success_result = False
                cert_status = (
                    "ignored, certificates for required courses are missing, use "
                    "-f or --force argument to forcefully create a program certificate"
                )

            result_summary = "Certificate: {}".format(cert_status)

            result = "Processed user {} ({}) in program {}. Result - {}".format(
                user.username,
                user.email,
                program.readable_id,
                result_summary,
            )
            result_output = self.style.SUCCESS(result)
            if not success_result:
                result_output = self.style.ERROR(result)
            self.stdout.write(result_output)
