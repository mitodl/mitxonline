"""Promote/demote a user."""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    """Promote/demote a user."""

    help = "Promote/demote a user."

    def add_arguments(self, parser):
        """Add arguments to the command."""

        parser.add_argument(
            "email",
            type=str,
            help="The email of the user to promote/demote.",
        )

        parser.add_argument(
            "--promote",
            action="store_true",
            help="Promote the user to staff.",
        )

        parser.add_argument(
            "--demote",
            action="store_true",
            help="Demote the user from staff.",
        )

        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Promote the user to superuser.",
        )

    def handle(self, **options) -> None:
        """Handle the command."""

        email = options["email"]
        promote = options["promote"]
        demote = options["demote"]
        superuser = options["superuser"]
        verb = ""

        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            errmsg = f"User with email {email} does not exist."
            raise CommandError(errmsg) from exc

        if promote and demote:
            errmsg = "You cannot provide both --promote and --demote."
            raise CommandError(errmsg)

        if promote:
            verb = "promoted"
            user.is_staff = True

            if superuser:
                verb = f"{verb} to superuser"
                user.is_superuser = True

            user.save()
        elif demote:
            verb = "demoted"
            # Demoting a superuser just makes them staff.
            if superuser:
                verb = f"{verb} from superuser to staff"
                user.is_staff = True
                user.is_superuser = False
            else:
                user.is_staff = False
                user.is_superuser = False

            user.save()
        else:
            errmsg = "You must provide either --promote or --demote."
            raise CommandError(errmsg)

        self.stdout.write(self.style.SUCCESS(f"Successfully {verb} user {user.email}."))
