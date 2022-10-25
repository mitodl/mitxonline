"""
Creates a new user in MITx Online, and their associated edX account.

Note that this depends on the `create_enrollment` command - this will call that
to generate the enrollments if specified (rather than reinventing the wheel).
"""

from argparse import RawTextHelpFormatter
from getpass import getpass

from django.core.management import BaseCommand
from django.core.management import call_command
from django.db.models import Q

from mail.api import validate_email_addresses
from users.models import User, LegalAddress, validate_iso_3166_1_code


class Command(BaseCommand):
    """
    Creates a new user in MITx Online, and their associated edX account.
    """

    help = """Creates a new user in MITx Online, and creates an associated edX account (if there's working edX integration set up).
    
    To create a new user, specify the following options:
    create_user <email> <first name> <last name> <display name> <country code> [--enroll <courseware id>]
    where:
    - email: the new learner's email address
    - first name, last name, display name: the name to associate with the new account
    - country code: the ISO-3166 Alpha-2 code for the learner's country (defaults to US)
    
    You will be prompted for the password.

    Optionally, specify --enroll and a courseware ID (course-v1:MITx+stuff) to enroll the new learner in the specified object. Specify this as many times as necessary. 
    """

    def create_parser(self, prog_name, subcommand):  # pylint: disable=arguments-differ
        """
        create parser to add new line in help text.
        """
        parser = super().create_parser(prog_name, subcommand)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        """parse arguments"""

        # pylint: disable=expression-not-assigned
        parser.add_argument(
            "username",
            help="Username for the learner to create.",
        )

        parser.add_argument(
            "email",
            help="Email address of the learner to create.",
        )

        parser.add_argument("firstname", help="The learner's first name.", type=str)

        parser.add_argument("lastname", help="The learner's last name.", type=str)

        parser.add_argument("displayname", help="The learner's display name.", type=str)

        parser.add_argument(
            "countrycode",
            help="The country code to use. (Default US)",
            type=str,
            default="US",
        )

        parser.add_argument(
            "--enroll",
            action="append",
            nargs="?",
            type=str,
            help="Optionally enroll the new user in the specified courseware.",
        )

    def handle(self, *args, **kwargs):
        if User.objects.filter(
            Q(username=kwargs["username"]) | Q(email=kwargs["email"])
        ).exists():
            self.stderr.write(
                f"User with username {kwargs['username']} or email address {kwargs['email']} already exists."
            )
            exit(-1)

        validate_iso_3166_1_code(kwargs["countrycode"])
        validate_email_addresses([kwargs["email"]])

        password = getpass(
            f'Creating user {kwargs["username"]}. Please enter their new password: '
        )

        new_account = User.objects.create_user(
            kwargs["username"], kwargs["email"], password
        )

        new_account.name = kwargs["displayname"]
        new_account.is_staff = False
        new_account.is_active = True
        new_account.is_superuser = False
        new_account.save()

        new_account.legal_address.first_name = kwargs["firstname"]
        new_account.legal_address.last_name = kwargs["lastname"]
        new_account.legal_address.country = kwargs["countrycode"]

        self.stdout.write(self.style.SUCCESS(f"Created user {new_account.username}."))

        if kwargs["enroll"] is not None and len(kwargs["enroll"]) > 0:
            for courseware in kwargs["enroll"]:
                call_command(
                    "create_enrollment",
                    user=new_account.username,
                    run=courseware,
                    keep_failed_enrollments=True,
                )
