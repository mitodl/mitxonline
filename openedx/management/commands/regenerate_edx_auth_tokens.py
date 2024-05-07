"""
Clears and regenerates the OAuth tokens for the specified learner.
"""

from argparse import RawTextHelpFormatter

from django.core.management import BaseCommand

from openedx.api import create_edx_auth_token
from openedx.constants import PLATFORM_EDX
from openedx.models import OpenEdxApiAuth
from users.api import fetch_users


class Command(BaseCommand):
    """
    Clears and regenerates the OAuth tokens for the specified learner.
    """

    help = "Clears and regenerates the OAuth tokens for the specified learner."

    def create_parser(self, prog_name, subcommand):  # pylint: disable=arguments-differ
        """
        create parser to add new line in help text.
        """
        parser = super().create_parser(prog_name, subcommand)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            action="store",
            help="The ID, username or email address to reset.",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        self.stdout.write(f"Looking for {kwargs['username']}...")

        user = fetch_users([kwargs["username"]])

        if user is None or user.count() == 0:
            self.stderr.write(
                self.style.ERROR(f"Could not find user {kwargs['username']}.")
            )
        elif user.count() > 1:
            self.stderr.write(self.style.ERROR(f"Ambiguous ID {kwargs['username']}."))
        else:
            user = user.get()

            if user.openedx_users.filter(platform=PLATFORM_EDX).count() == 0:
                self.stderr.write(
                    self.style.ERROR(
                        f"No OpenEdxUser for {user.username}. Run repair instead."
                    )
                )
                return

            self.stdout.write(
                f"Regenerating Open edX auth tokens for {user.username}..."
            )

            OpenEdxApiAuth.objects.filter(user=user).delete()
            create_edx_auth_token(user)

            new_tokens = OpenEdxApiAuth.objects.filter(user=user).get()

            self.stdout.write(
                f"Done! New refresh token {new_tokens.refresh_token} and new access token {new_tokens.access_token} creatd."
            )
