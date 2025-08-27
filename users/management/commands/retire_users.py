"""
Retire user(s) from MITx Online and user initiate retirement on edX
"""

import sys
from argparse import RawTextHelpFormatter
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from social_django.models import UserSocialAuth
from user_util import user_util

from authentication.utils import block_user_email
from main import settings
from openedx.api import bulk_retire_edx_users
from users.api import fetch_users

User = get_user_model()

RETIRED_USER_SALTS = ["mitx-online-retired-email"]
RETIRED_EMAIL_FMT = (
    "retired_email_{}@retired." + f"{urlparse(settings.SITE_BASE_URL).netloc}"
)


class Command(BaseCommand):
    """
    Retire user from MITx Online
    """

    help = """
    Retire one or multiple users. Username or email can be used to identify a user.

    For single user use:\n
    `./manage.py retire_users --user=foo` or do \n
    `./manage.py retire_users -u foo` \n or do \n
    `./manage.py retire_users -u foo@email.com` \n or do \n

    For multiple users, add arg `--user` for each user i.e:\n
    `./manage.py retire_users --user=foo --user=bar --user=baz` or do \n
    `./manage.py retire_users --user=foo@email.com --user=bar@email.com --user=baz` or do \n
    `./manage.py retire_users -u foo -u bar -u baz`

    For blocking user(s) use --block option:\n
    `./manage.py retire_users --user=foo@email.com --block` or do \n
    `./manage.py retire_users -u foo@email.com -b` \n or do \n

    For retiring a user who doesn't have an edX account, use the `--no-edx` option to retire user anyway:\n
    ./manage.py retire_users --user=foo@email.com --no-edx \n
    """

    def create_parser(self, prog_name, subcommand):  # pylint: disable=arguments-differ
        """
        Create parser to add new line in help text.
        """
        parser = super().create_parser(prog_name, subcommand)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        """Parse arguments"""

        # pylint: disable=expression-not-assigned
        parser.add_argument(
            "-u",
            "--user",
            action="append",
            default=[],
            dest="users",
            help="Single or multiple username(s) or email(s)",
        )

        parser.add_argument(
            "-b",
            "--block",
            action="store_true",
            dest="block_users",
            help="If provided, user's email will be hashed and added to the blocklist",
        )

        parser.add_argument(
            "-e",
            "--no-edx",
            action="store_true",
            dest="no_edx",
            help="If provided, user will be retired even if they do not have an edX account",
        )

    def get_retired_email(self, email):
        """Convert user email to retired email format."""
        return user_util.get_retired_email(email, RETIRED_USER_SALTS, RETIRED_EMAIL_FMT)

    def handle(self, *args, **kwargs):  # noqa: ARG002
        users = kwargs.get("users", [])
        block_users = kwargs.get("block_users")
        no_edx = kwargs.get("no_edx", False)

        if not users:
            self.stderr.write(
                self.style.ERROR(
                    "No user(s) provided. Please provide user(s) using -u or --user."
                )
            )
            sys.exit(1)

        users = fetch_users(kwargs["users"])

        for user in users:
            self.stdout.write(f"Retiring user: {user}")
            if not user.is_active:
                self.stdout.write(
                    self.style.ERROR(
                        f"User: '{user}' is already deactivated in MITx Online"
                    )
                )
                continue
            if not no_edx:
                resp = bulk_retire_edx_users(user.edx_username)
                if user.edx_username not in resp["successful_user_retirements"]:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Could not initiate retirement request on edX for user {user}"
                        )
                    )
                    continue
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Retirement request initiated on edX for User: '{user}'"
                        )
                    )

            user.is_active = False

            # Change user password & email
            email = user.email

            if block_users:
                msg = block_user_email(email=email)
                if msg:
                    self.stdout.write(self.style.SUCCESS(msg))

            user.email = self.get_retired_email(user.email)
            user.set_unusable_password()
            user.save()

            self.stdout.write(
                f"Email changed from {email} to {user.email} and password is not useable now"
            )

            # reset user social auth
            auth_deleted_count = UserSocialAuth.objects.filter(user=user).delete()

            if auth_deleted_count:
                self.stdout.write(f"For  user: '{user}' SocialAuth rows deleted")

            self.stdout.write(
                self.style.SUCCESS(f"User: '{user}' is retired from MITx Online")
            )
