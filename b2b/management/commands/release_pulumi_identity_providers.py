"""
Let the provisioning API change identity providers Pulumi no longer declares.

adopt_keycloak_identity_providers records Pulumi's IdPs as pulumi_managed, and
the provisioning API refuses to change those. Run this for each IdP once it is
out of Pulumi state (its block removed from olapps.py and deployed with
retain_on_delete), so the dashboard can manage it.
"""

from django.core.management import BaseCommand, CommandError

from b2b.models import OrganizationIdentityProvider
from b2b.provisioning import release_pulumi_identity_provider


class Command(BaseCommand):
    help = "Release identity providers that have left Pulumi state."

    def add_arguments(self, parser):
        parser.add_argument("aliases", nargs="+", help="The IdP aliases to release.")

    def handle(self, *args, **options):  # noqa: ARG002
        identity_providers = OrganizationIdentityProvider.objects.filter(
            alias__in=options["aliases"]
        )
        missing = set(options["aliases"]) - set(
            identity_providers.values_list("alias", flat=True)
        )
        if missing:
            msg = "No recorded identity provider for: " + ", ".join(sorted(missing))
            raise CommandError(msg)

        for identity_provider in identity_providers.order_by("alias"):
            release_pulumi_identity_provider(identity_provider)
            self.stdout.write(
                self.style.SUCCESS(f"Released: {identity_provider.alias}")
            )
