"""
Record the identity providers ol-infrastructure created in Keycloak.

The staff dashboard lists an organization's IdPs from OrganizationIdentityProvider
rows, and only the provisioning API wrote those, so every IdP Pulumi declared
was invisible there. This records each IdP Keycloak links to an organization
here, without changing anything in Keycloak. Safe to re-run: recorded IdPs are
skipped.

Until an IdP leaves Pulumi state, the next pulumi up reverts any change made to
it through the dashboard.
"""

import logging

from django.core.management import BaseCommand, CommandError

from b2b.exceptions import IdentityProviderNotAdoptableError
from b2b.models import OrganizationPage
from b2b.provisioning import (
    KeycloakConnection,
    adopt_identity_provider,
    find_unadopted_identity_providers,
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Record the identity providers Keycloak links to organizations here."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be recorded without writing anything.",
        )
        parser.add_argument(
            "org_keys",
            nargs="*",
            help="Limit the run to these org keys. Defaults to every linked org.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        organizations = OrganizationPage.objects.all()
        if options["org_keys"]:
            organizations = organizations.filter(org_key__in=options["org_keys"])
            unmatched = set(options["org_keys"]) - set(
                organizations.filter(sso_organization_id__isnull=False).values_list(
                    "org_key", flat=True
                )
            )
            if unmatched:
                self.stderr.write(
                    "No organization linked to Keycloak for: "
                    + ", ".join(sorted(unmatched))
                )

        connection = KeycloakConnection()
        candidates = find_unadopted_identity_providers(connection, organizations)
        if not candidates:
            self.stdout.write("No unrecorded identity providers found.")
            return

        failed = []
        for organization, keycloak_idp in candidates:
            label = f"{keycloak_idp.alias} ({keycloak_idp.provider_id}) for {organization.org_key}"

            if options["dry_run"]:
                state = "enabled" if keycloak_idp.enabled else "disabled"
                self.stdout.write(f"Would record: {label}, {state} in Keycloak")
                continue

            try:
                identity_provider = adopt_identity_provider(organization, keycloak_idp)
            except IdentityProviderNotAdoptableError as exc:
                failed.append(keycloak_idp.alias)
                self.stderr.write(f"Skipped {label}: {exc}")
            except Exception as exc:
                # One IdP's failure must not stop the rest of the batch.
                log.exception("Could not record %s", keycloak_idp.alias)
                failed.append(keycloak_idp.alias)
                self.stderr.write(f"Failed {label}: {exc}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Recorded: {label} as {identity_provider.lifecycle_state}"
                    )
                )

        if failed:
            msg = (
                f"{len(failed)} identity provider(s) not recorded: {', '.join(failed)}"
            )
            raise CommandError(msg)
