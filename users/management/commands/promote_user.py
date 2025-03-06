"""Promote/demote a user."""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    """Promote/demote a user."""

    help = "Promote/demote a user."

    def add_arguments(self, parser):
        """Add arguments to the command."""

        subparsers = parser.add_subparsers(
            title="Action",
            dest="subcommand",
            required=True,
        )

        promote_parser = subparsers.add_parser("promote", help="Promote a user.")
        demote_parser = subparsers.add_parser("demote", help="Demote a user.")

        promote_parser.add_argument(
            "--superuser",
            action="store_true",
            help="Promote the user to superuser.",
        )
        promote_parser.add_argument(
            "--email",
            type=str,
            help="The email of the user to promote/demote.",
            required=True,
        )

        demote_parser.add_argument(
            "--staff",
            action="store_true",
            help="Demote the user from superuser to staff.",
        )
        demote_parser.add_argument(
            "--email",
            type=str,
            help="The email of the user to promote/demote.",
            required=True,
        )

    def _get_user(self, email: str) -> get_user_model:
        """Get a user by email."""

        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            errmsg = f"User with email {email} does not exist."
            raise CommandError(errmsg) from exc

        return user

    def handle_promote(self, *args, **options) -> None:  # noqa: ARG002
        """Handle user promotion."""

        email = options["email"]
        superuser = options["superuser"]

        user = self._get_user(email)

        user.is_staff = True
        user.is_superuser = superuser

        user.save()

        superuser_str = " to superuser" if superuser else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully promoted user {user.email}{superuser_str}."
            )
        )

    def handle_demote(self, *args, **options) -> None:  # noqa: ARG002
        """Handle user demotion."""

        email = options["email"]
        staff = options["staff"]

        user = self._get_user(email)

        user.is_staff = staff and user.is_superuser
        user.is_superuser = False

        user.save()

        staff_str = " from superuser to staff" if staff else ""
        self.stdout.write(
            self.style.SUCCESS(f"Successfully demoted user {user.email}{staff_str}.")
        )

    def handle(self, **options) -> None:
        """Handle the command."""

        subcommand = options["subcommand"]

        if subcommand == "promote":
            self.handle_promote(**options)
        elif subcommand == "demote":
            self.handle_demote(**options)
        else:
            errmsg = "You must specify promote or demote."
            raise CommandError(errmsg)
