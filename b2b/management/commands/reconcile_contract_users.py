"""
Sync managed contract membership with org membership.

This is an all-or-nothing operation.
"""

import logging

from django.core.management import BaseCommand

from b2b.models import OrganizationPage

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync managed contract membership with org membership."

    def handle(self, *args, **options):  # noqa: ARG002
        """Loop through the orgs and run reconcile_all_user_contracts on them."""

        for org in OrganizationPage.objects.all():
            self.stdout.write(f"Reconciling org {org.slug}...")

            org.reconcile_all_user_contracts()
