"""Management command to decrypt a user's ExportComplianceLog record"""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from nacl.encoding import Base64Encoder
from nacl.public import PrivateKey

from compliance.api import decrypt_export_compliance_log
from compliance.models import ExportComplianceLog

User = get_user_model()


class Command(BaseCommand):
    """Decrypts the most recent ExportComplianceLog record for a user"""

    help = "Decrypts the most recent ExportComplianceLog record for a user"

    def add_arguments(self, parser):
        """Add arguments to the command."""
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--user-id", help="the id of the user")
        group.add_argument("--email", help="the email of the user")
        group.add_argument("--username", help="the username of the user")

    def _get_user(self, options):
        """Look up the user by whichever identifier was provided."""
        if options["user_id"]:
            return User.objects.get(id=options["user_id"])
        if options["username"]:
            return User.objects.get(username=options["username"])
        return User.objects.get(email=options["email"])

    def handle(self, *args, **options):  # noqa: ARG002
        try:
            user = self._get_user(options)
        except User.DoesNotExist as exc:
            errmsg = "User doesn't exist"
            raise CommandError(errmsg) from exc

        export_compliance_log = (
            ExportComplianceLog.objects.filter(user=user)
            .order_by("-created_on")
            .first()
        )

        if export_compliance_log is None:
            errmsg = "User has no ExportComplianceLog records"
            raise CommandError(errmsg)

        encoded_private_key = input("NaCl Private Key (Base64-encoded): ")
        private_key = PrivateKey(encoded_private_key, encoder=Base64Encoder)
        decrypted = decrypt_export_compliance_log(export_compliance_log, private_key)

        self.stdout.write(
            self.style.SUCCESS(
                f"Courseware object: {export_compliance_log.courseware_object}"
            )
        )
        self.stdout.write(self.style.SUCCESS("Request:"))
        self.stdout.write("------------------------------------------------------")
        self.stdout.write(self.style.SUCCESS(decrypted.request))
        self.stdout.write("------------------------------------------------------")
        self.stdout.write(self.style.SUCCESS(""))
        self.stdout.write(self.style.SUCCESS("Response:"))
        self.stdout.write("------------------------------------------------------")
        self.stdout.write(self.style.SUCCESS(decrypted.response))
        self.stdout.write("------------------------------------------------------")
