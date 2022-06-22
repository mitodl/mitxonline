import sys
import unicodedata
from argparse import RawTextHelpFormatter

from django.core.management import BaseCommand

from users.models import User


class Command(BaseCommand):
    """Finds usernames that would cause conflicts after normalization"""

    help = """
  Finds usernames that would cause conflicts after normalization. 
  """

    def make_normalized_username(self, username):
        """Strips non-ASCII characters from the username."""
        normalized_username = unicodedata.normalize("NFD", username)
        normalized_username = normalized_username.encode("ascii", "ignore").decode(
            "utf-8"
        )
        return str(normalized_username)

    def create_parser(self, prog_name, subcommand):  # pylint: disable=arguments-differ
        """
        create parser to add new line in help text.
        """
        parser = super().create_parser(prog_name, subcommand)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def handle(self, *args, **kwargs):
        all_users = User.objects.only("id", "username").all()
        username_lookup = {}

        for user in all_users:
            normalized_username = self.make_normalized_username(user.username)
            if normalized_username not in username_lookup:
                username_lookup[normalized_username] = [user.id]
            else:
                username_lookup[normalized_username].append(user.id)

        conflicts = [x for x in username_lookup if len(x) > 0]

        for conflict in conflicts:
            if len(username_lookup[conflict]) > 1:
                self.stdout.write(
                    "Username {} has conflicts: {}".format(
                        conflict, " ".join(map(str, username_lookup[conflict]))
                    )
                )
