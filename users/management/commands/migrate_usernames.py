"""
Set username to the lowercased email for users whose username is anything else.

Keycloak lowercases usernames, and its username in the olapps realm is the
email. scim-for-keycloak finds a user it has no stored id for with
`userName eq "<email>"`, which compares against username exactly. A user whose
username is anything else, including the email in another case, can't be found,
so their SCIM operations fail with a 409 and retry indefinitely.

A user is skipped when their email is already another user's username (ignoring
case). Those users are listed by id for manual review.

Reports what would change by default. Pass --apply to rename.
"""

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from django.db.models import Exists, F, OuterRef
from django.db.models.functions import Lower

User = get_user_model()

UPDATE_BATCH_SIZE = 5000


def _mismatched_users():
    """Users with an email whose username isn't that email lowercased"""
    return (
        User.objects.annotate(lower_email=Lower("email"))
        .exclude(email="")
        .exclude(username=F("lower_email"))
    )


def _renameable_users():
    """Mismatched users whose lowercased email can't collide with anyone"""
    others = User.objects.exclude(pk=OuterRef("pk"))
    return _mismatched_users().exclude(
        Exists(
            others.annotate(lower_username=Lower("username")).filter(
                lower_username=OuterRef("lower_email")
            )
        )
    )


def rename_users():
    """
    Set username to the lowercased email for every user where that can't collide.

    Renaming one user can clear the way for another (their email was the first
    user's old username), so this repeats until a pass changes nothing. Each
    batch commits on its own, so a run holds no row locks between batches, and
    an interrupted run can be repeated.

    :returns: how many users were renamed
    :rtype: int
    """
    renamed = 0
    while user_ids := list(_renameable_users().values_list("pk", flat=True)):
        for start in range(0, len(user_ids), UPDATE_BATCH_SIZE):
            renamed += User.objects.filter(
                pk__in=user_ids[start : start + UPDATE_BATCH_SIZE]
            ).update(username=Lower("email"))
    return renamed


class Command(BaseCommand):
    """Set username to the lowercased email where it is something else"""

    help = __doc__

    def add_arguments(self, parser):
        """Define the command's CLI flags"""
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Rename the users. Without this, only report what would change.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Rename users, or report how many would be renamed"""
        if not options["apply"]:
            self.stdout.write(
                f"{_mismatched_users().count()} users have a username other "
                f"than their lowercased email, and "
                f"{_renameable_users().count()} of them can be renamed now. "
                "Renaming those can clear the way for others. "
                "Pass --apply to rename them."
            )
            return

        self.stdout.write(self.style.SUCCESS(f"Renamed {rename_users()} users"))
        skipped_ids = list(
            _mismatched_users().order_by("pk").values_list("pk", flat=True)
        )
        if skipped_ids:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(skipped_ids)} users need manual review, because "
                    "their email is already another user's username: "
                    + ", ".join(map(str, skipped_ids))
                )
            )
