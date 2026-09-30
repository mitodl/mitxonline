"""
Push MITx Online organizations that have no Keycloak organization into Keycloak.

Organizations that predate the provisioning API have no sso_organization_id,
so attach_user() no-ops for them and they cannot be managed through the staff
dashboard. This links each one to an existing realm organization with the same
alias, or creates one. Safe to re-run: linked organizations are skipped.
"""

import logging

from django.core.management import BaseCommand, CommandError

from b2b.models import OrganizationPage
from b2b.provisioning import KeycloakConnection, link_organization_to_keycloak

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create or adopt a Keycloak organization for each unlinked organization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created or adopted without writing anything.",
        )
        parser.add_argument(
            "org_keys",
            nargs="*",
            help="Limit the run to these org keys. Defaults to every unlinked org.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        organizations = OrganizationPage.objects.filter(
            sso_organization_id__isnull=True
        )
        if options["org_keys"]:
            organizations = organizations.filter(org_key__in=options["org_keys"])

        connection = KeycloakConnection()
        realm_aliases = {
            org.alias.lower()
            for org in connection.organizations.list_all()
            if org.alias is not None
        }

        unmatched = set(options["org_keys"]) - set(
            organizations.values_list("org_key", flat=True)
        )
        if unmatched:
            self.stderr.write(
                "No unlinked organization for: " + ", ".join(sorted(unmatched))
            )

        failed = []
        for organization in organizations.order_by("org_key"):
            action = (
                "adopt" if organization.org_key.lower() in realm_aliases else "create"
            )

            if options["dry_run"]:
                self.stdout.write(f"Would {action}: {organization.org_key}")
                continue

            try:
                created = link_organization_to_keycloak(
                    organization, connection=connection
                )
            except Exception as exc:
                # One org's failure (Keycloak, an alias collision, an invalid
                # legacy page) must not stop the rest of the batch.
                log.exception("Could not link %s", organization.org_key)
                failed.append(organization.org_key)
                self.stderr.write(f"Failed {organization.org_key}: {exc}")
            else:
                outcome = "Created" if created else "Adopted"
                self.stdout.write(
                    self.style.SUCCESS(f"{outcome}: {organization.org_key}")
                )

        if failed:
            msg = f"{len(failed)} organization(s) failed: {', '.join(failed)}"
            raise CommandError(msg)
