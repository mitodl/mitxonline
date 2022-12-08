"""
Management command to revoke, un revoke or create a certificate for a program for the given User.

Check the usages of this command below:

**Certificate Creation**

1. Generate Pogram certificate for a user
./manage.py manage_program_certificates —-create -—program=<program_readable_id> -—user=<username or email>

**Revoke/Un-revoke Certificates**

2. Revoke a certificate for a user
./mange.py manage_program_certificates -—revoke -—user=<username or email> -—program=<program_readable_id>

3. Un-Revoke a certificate for a user
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

    help = (
        "Revoke, un revoke or create a certificate for a program for the given User "
        "or Users when no user is provided"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email or username of the enrolled User",
            required=True,
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--program", type=str, help="The 'readable_id' value for a Program"
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

        super().add_arguments(parser)

    def handle(self, *args, **options):  # pylint: disable=too-many-locals
        """Handle command execution"""

        revoke = options.get("revoke")
        unrevoke = options.get("unrevoke")
        create = options.get("create")
        program = options.get("program")

        if not (revoke or unrevoke) and not create:
            raise CommandError(
                "The command needs a valid action e.g. --revoke, --unrevoke, --create."
            )
        try:
            user = fetch_user(options["user"]) if options["user"] else None
        except User.DoesNotExist:
            user = None

        # A program is needed for revoke/un-revoke and certificate creation
        if not program:
            raise CommandError("The command needs a valid program.")

        # Unable to obtain a program object based on the provided courseware id
        try:
            program = Program.objects.get(readable_id=program)
        except Program.DoesNotExist:
            raise CommandError(
                "Could not find program with readable_id={}.".format(program)
            )

        # Handle revoke/un-revoke of a certificate
        if revoke or unrevoke:
            if not user:
                raise CommandError("Revoke/Un-revoke operation needs a valid user.")

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

        # Handle the creation of the certificates.
        # Also check if the certificate creation was requested with grade override. (Generally useful when we want to
        # create a certificate for a user while overriding the grade value)
        elif create:

            # While overriding grade we force create the certificate
            certificate, created_cert = generate_program_certificate(
                user=user,
                program=program,
            )

            if certificate and created_cert:
                cert_status = "created"
            elif certificate and not created_cert:
                cert_status = "already exists"
            else:
                cert_status = "ignored, certificates for requied courses are missing"

            result_summary = "Certificate: {}".format(cert_status)

            result = "Processed user {} ({}) in program {}. Result - {}".format(
                user.username,
                user.email,
                program.readable_id,
                result_summary,
            )

            self.stdout.write(self.style.SUCCESS(result))
