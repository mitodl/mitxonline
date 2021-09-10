"""
Management command to sync local enrollment records with edX
"""
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from openedx.api import sync_enrollments_with_edx
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """
    Management command to sync local enrollment records with edX
    """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the User",
            required=True,
        )

    def handle(self, *args, **options):
        """Walk all users who are missing records and repair them"""
        user = fetch_user(options["user"])
        self.stdout.write(
            f"Syncing enrollments for user '{user.username}' ({user.email})"
        )
        result = sync_enrollments_with_edx(user)
        if result.no_changes:
            self.stdout.write(self.style.SUCCESS("Sync completed with no changes."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created: {len(result.created)}\n"
                    f"Reactivated: {len(result.reactivated)}\n"
                    f"Deactivated: {len(result.deactivated)}\n"
                )
            )
