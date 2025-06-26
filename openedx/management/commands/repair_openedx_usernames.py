"""
Repairs the openedx username
"""

import sys

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand
from django.db.models import F, Q
from tabulate import tabulate

from openedx import api

User = get_user_model()


class Command(BaseCommand):
    """
    Repairs the openedx username
    """

    help = "Repairs the openedx username"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            action="append",
            help="The ID of the user to repair",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        users = User.objects.filter(
            Q(openedx_users=None) | Q(openedx_users__edx_username=None)
        ).exclude(Q(username=F("email")) | Q(username__icontains="@"))

        if kwargs["user_id"]:
            users = users.filter(id__in=kwargs["user_id"])

        if users.count() == 0:
            self.stdout.write("No users found")
            sys.exit(1)

        self.stdout.write("Found the following users:")
        self.stdout.write("")

        self.stdout.write(
            tabulate(
                [(user.email, user.username) for user in users],
                headers=["email", "username"],
            )
        )
        self.stdout.write("")

        answer = input("Continue to repair these users? (y/n): ").lower()

        if answer == "y":
            for user in users:
                api.create_user(user, user.username)
        else:
            self.stdout.write("No actions taken, exiting")
