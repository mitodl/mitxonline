"""
Management command to sync local profiles with edX
"""

import sys

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from openedx.api import update_edx_user_profile
from users.api import fetch_user
from users.models import User

User = get_user_model()  # noqa: F811


class Command(BaseCommand):
    """
    Syncs the user's profile with edX.
    """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the user to sync.",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Sync all users in the system (this may take a long time).",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if not options["all"] and "user" in options:
            try:
                users = [fetch_user(options["user"])]
            except User.DoesNotExist as exc:
                self.stderr.write(self.style.ERROR(f"{exc!s}"))
                sys.exit(1)
        elif options["all"]:
            users = User.objects.all()
        else:
            self.stderr.write(
                self.style.ERROR("Please specify a user or the --all flag.")
            )
            sys.exit(1)

        successes = failures = 0

        for user in users:
            self.stdout.write(f"Updating profile for '{user.username}' ({user.email})")

            try:
                result = update_edx_user_profile(user)  # noqa: F841
                successes += 1
            except Exception as e:  # noqa: BLE001
                self.stdout.write(
                    self.style.ERROR(
                        f"Sync did not complete successfully for user {user.username}: {e}"
                    )
                )
                failures += 1

        self.stdout.write(self.style.SUCCESS(f"{successes} updated successfully"))
        if failures > 0:
            self.stdout.write(self.style.ERROR(f"{failures} failed to update"))
