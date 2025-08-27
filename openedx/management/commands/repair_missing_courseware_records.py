"""
Management command to repair missing openedx records
"""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from mitol.common.utils import get_error_response_summary
from requests.exceptions import HTTPError

from openedx.api import repair_faulty_edx_user
from users.api import fetch_user

User = get_user_model()


class Command(BaseCommand):
    """
    Management command to repair missing openedx records
    """

    help = "Repairs missing openedx records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="The id, email, or username of the User",
            required=False,
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Walk all users who are missing records and repair them"""
        user_attr = options.get("user")
        if user_attr is not None:
            user = fetch_user(user_attr)
            self.stdout.write(f"Repairing user '{user.edx_username}' ({user.email})")
            users = [user]
        else:
            users_to_repair = User.faulty_openedx_users.all()
            self.stdout.write(f"Repairing {users_to_repair.count()} users")
            users = User.faulty_users_iterator()

        error_count = 0
        success_count = 0

        for user in users:
            result = []
            try:
                created_user, created_auth_token = repair_faulty_edx_user(user)
            except HTTPError as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"{user.edx_username} ({user.email}): "
                        f"Failed to repair ({get_error_response_summary(exc.response)})"
                    )
                )
                error_count += 1
            except Exception as exc:  # pylint: disable=broad-except  # noqa: BLE001
                self.stderr.write(
                    self.style.ERROR(
                        f"{user.edx_username} ({user.email}): Failed to repair (Exception: {exc!s})"
                    )
                )
                error_count += 1
            else:
                if created_user:
                    result.append("Created edX user")
                if created_auth_token:
                    result.append("Created edX auth token")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{user.edx_username} ({user.email}): {', '.join(result)}"
                    )
                )
                success_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Repair Complete: {success_count} repaired, {error_count} failures"
            )
        )
