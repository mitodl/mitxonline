"""
Change users' usernames so that they match their email addresses.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Change users' usernames so that they match their email addresses..
    """

    help = "Update users' usernames to match their email addresses."
    MIGRATE_USERNAME_BATCH_SIZE = 1000

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Set the username to the email address"""

        User = get_user_model()
        max_length = User._meta.get_field("username").max_length  # noqa: SLF001

        users = User.objects.order_by("id").values("id", "email", "username").all()
        total_users = users.count()
        skipped_users = 0
        already_migrated_users = 0

        for start in range(0, total_users, self.MIGRATE_USERNAME_BATCH_SIZE):
            batch = users[start : start + self.MIGRATE_USERNAME_BATCH_SIZE]
            updates = []
            new_usernames = []

            for user in batch:
                new_username = user["email"][:max_length]
                if user["username"] == new_username:
                    # If the user is already migrated, don't do it again.
                    msg = f"User {user['id']} already has username {new_username}. Skipping update."
                    log.info(msg)
                    already_migrated_users += 1
                else:
                    updates.append(User(id=user["id"], username=new_username))
                    new_usernames.append(new_username)

            try:
                with transaction.atomic():
                    User.objects.bulk_update(updates, ["username"])
            except IntegrityError:
                # There was a username collision - step through this batch
                # and update one at a time so we can figure out who it was
                for user, new_username in zip(updates, new_usernames):
                    if User.objects.filter(username=new_username).exists():
                        msg = f"Username {new_username} already exists for user {user.id}. Skipping update."
                        self.stdout.write(self.style.WARNING(msg))
                        log.warning(msg)
                        skipped_users += 1
                    else:
                        User.objects.filter(pk=user.id).update(username=new_username)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {total_users - skipped_users - already_migrated_users}. {already_migrated_users} users were already migrated."
            )
        )

        if skipped_users:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {skipped_users} users due to username collisions."
                )
            )
