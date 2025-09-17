"""
Sync organizations from Keycloak.

This is an all-or-nothing operation.
"""

import logging

from django.core.management import BaseCommand

from b2b.api import reconcile_keycloak_orgs

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync organizations from Keycloak."

    def handle(self, *args, **options):  # noqa: ARG002
        created, updated = reconcile_keycloak_orgs()
        log.info("Created %d orgs, updated %d orgs", created, updated)
