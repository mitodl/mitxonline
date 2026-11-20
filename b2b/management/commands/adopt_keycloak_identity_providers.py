"""
Record the identity providers ol-infrastructure created in Keycloak.

The staff dashboard lists an organization's IdPs from OrganizationIdentityProvider
rows, and only the provisioning API wrote those, so every IdP Pulumi declared
was invisible there. This records each IdP Keycloak links to an organization
here, without changing anything in Keycloak. Safe to re-run: recorded IdPs are
skipped. So is an IdP Keycloak links to more than one organization, because a
delete through one organization's record would remove it for all of them.

Recorded IdPs are pulumi_managed: the dashboard lists them, and the provisioning
API refuses to change them until release_pulumi_identity_providers runs for
each one after it leaves Pulumi state.
"""

import logging
from collections import defaultdict
from pathlib import Path

from django.core.management import BaseCommand, CommandError

from b2b.exceptions import IdentityProviderNotAdoptableError
from b2b.models import OrganizationIdentityProvider, OrganizationPage
from b2b.provisioning import (
    KeycloakConnection,
    adopt_identity_provider,
    adoption_metadata_source,
    organization_identity_providers,
)

log = logging.getLogger(__name__)


def _parse_source(value):
    """Turn ALIAS=URL or ALIAS=PATH into (alias, metadata source)."""

    alias, separator, source = value.partition("=")
    if not separator or not alias or not source:
        msg = f"--source takes ALIAS=URL or ALIAS=PATH, not {value!r}."
        raise CommandError(msg)
    if not source.startswith(("http://", "https://")):
        # A saved SAML metadata document, e.g. one of the
        # files/olapps/*_metadata.xml copies in ol-infrastructure.
        try:
            source = Path(source).read_text()
        except OSError as exc:
            msg = f"--source {alias}: could not read {source}: {exc.strerror}"
            raise CommandError(msg) from exc
    return alias, source


class Command(BaseCommand):
    help = "Record the identity providers Keycloak links to organizations here."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be recorded without writing anything.",
        )
        parser.add_argument(
            "--source",
            action="append",
            default=[],
            metavar="ALIAS=URL_OR_PATH",
            help=(
                "The metadata URL, or a file holding the metadata XML, to record "
                "for an IdP whose source Keycloak doesn't hold (configured from "
                "inline XML) or holds wrongly (an OIDC discovery URL that isn't "
                "under its issuer). Repeatable."
            ),
        )
        parser.add_argument(
            "org_keys",
            nargs="*",
            help=(
                "Record only these orgs' IdPs. Every linked org is still read, "
                "to find IdPs shared with another org. Defaults to every linked org."
            ),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        sources = dict(_parse_source(value) for value in options["source"])
        connection = KeycloakConnection()
        targets = self._target_org_keys(options["org_keys"])
        recorded = set(
            OrganizationIdentityProvider.objects.values_list("alias", flat=True)
        )
        links, failed = self._links(connection)
        skipped = []

        for alias, linked in links.items():
            org_keys = [organization.org_key for organization, _ in linked]
            if alias in recorded or not targets.intersection(org_keys):
                continue
            if len(linked) > 1:
                self.stderr.write(
                    f"Skipped {alias}: Keycloak links it to {', '.join(org_keys)}, "
                    "and deleting it through one of them would remove it for all."
                )
                skipped.append(alias)
                continue
            organization, keycloak_idp = linked[0]
            outcome = self._adopt(
                organization, keycloak_idp, sources, dry_run=options["dry_run"]
            )
            if outcome == "skipped":
                skipped.append(alias)
            elif outcome == "failed":
                failed.append(alias)

        # An organization whose listing failed would make its IdPs look unlinked.
        if not options["org_keys"] and not failed:
            self._report_unlinked(connection, recorded | set(links))
        self._report_outcome(sources, set(links), skipped, failed)

    def _links(self, connection):
        """
        Map each alias to the (organization, IdP) pairs Keycloak links it to.

        Returns:
        - dict[str, list[tuple]]: the links, in org_key order
        - list[str]: the org keys whose IdPs could not be listed
        """

        links = defaultdict(list)
        failed = []
        for organization in OrganizationPage.objects.filter(
            sso_organization_id__isnull=False
        ).order_by("org_key"):
            try:
                linked = organization_identity_providers(connection, organization)
            except Exception as exc:
                # One organization's Keycloak error must not stop the rest.
                log.exception("Could not list the IdPs of %s", organization.org_key)
                failed.append(organization.org_key)
                self.stderr.write(f"Failed to list {organization.org_key}: {exc}")
                continue
            for keycloak_idp in linked:
                links[keycloak_idp.alias].append((organization, keycloak_idp))
        return links, failed

    def _report_outcome(self, sources, linked_aliases, skipped, failed):
        """Report unused --source aliases and skipped IdPs, then fail on errors."""

        unused_sources = sorted(set(sources) - linked_aliases)
        if unused_sources:
            self.stderr.write(
                "--source given for IdPs no organization here links to "
                "(aliases are case-sensitive): " + ", ".join(unused_sources)
            )
        if skipped:
            # Not a failure: re-run with --source for the SAML ones.
            self.stderr.write(
                f"{len(skipped)} identity provider(s) not recorded (see above): "
                + ", ".join(skipped)
            )
        if failed:
            msg = f"{len(failed)} failure(s): {', '.join(failed)}"
            raise CommandError(msg)

    def _target_org_keys(self, org_keys):
        """Return the linked org keys to record IdPs for, reporting unknown keys."""

        linked = set(
            OrganizationPage.objects.filter(
                sso_organization_id__isnull=False
            ).values_list("org_key", flat=True)
        )
        if not org_keys:
            return linked

        unmatched = set(org_keys) - linked
        if unmatched:
            self.stderr.write(
                "No organization linked to Keycloak for: "
                + ", ".join(sorted(unmatched))
            )
        return linked.intersection(org_keys)

    def _adopt(self, organization, keycloak_idp, sources, *, dry_run):
        label = (
            f"{keycloak_idp.alias} ({keycloak_idp.provider_id}) "
            f"for {organization.org_key}"
        )

        if dry_run:
            try:
                adoption_metadata_source(keycloak_idp, sources.get(keycloak_idp.alias))
            except IdentityProviderNotAdoptableError as exc:
                self.stderr.write(f"Would skip {label}: {exc}")
                return "skipped"
            state = "enabled" if keycloak_idp.enabled else "disabled"
            self.stdout.write(f"Would record: {label}, {state} in Keycloak")
            return "dry-run"

        try:
            identity_provider = adopt_identity_provider(
                organization,
                keycloak_idp,
                metadata_source=sources.get(keycloak_idp.alias),
            )
        except IdentityProviderNotAdoptableError as exc:
            self.stderr.write(f"Skipped {label}: {exc}")
            return "skipped"
        except Exception as exc:
            # One IdP's failure must not stop the rest of the batch.
            log.exception("Could not record %s", keycloak_idp.alias)
            self.stderr.write(f"Failed {label}: {exc}")
            return "failed"

        self.stdout.write(
            self.style.SUCCESS(
                f"Recorded: {label} as {identity_provider.lifecycle_state}"
            )
        )
        return "recorded"

    def _report_unlinked(self, connection, seen):
        """List realm IdPs that no organization here links to."""

        unlinked = sorted(
            idp.alias
            for idp in connection.identity_providers.list_all()
            if idp.alias is not None and idp.alias not in seen
        )
        if unlinked:
            self.stdout.write(
                "Not linked to an organization here (not recorded): "
                + ", ".join(unlinked)
            )
