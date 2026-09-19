"""
Give the organizations that have no Keycloak UUID one.

Reports by default; nothing is written without --apply.
"""

from django.core.management import BaseCommand

from b2b.provisioning import BackfillAction, backfill_keycloak_organizations

APPLIED_VERBS = {BackfillAction.LINK: "linked", BackfillAction.CREATE: "created"}


class Command(BaseCommand):
    """Link, and optionally create, Keycloak organizations for unlinked orgs."""

    help = (
        "Link organizations that have no Keycloak UUID to the Keycloak "
        "organization with the same alias. Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        """Add the command's options."""

        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without this, only report what would happen.",
        )
        parser.add_argument(
            "--create-missing",
            action="store_true",
            help=(
                "Create a Keycloak organization for an org with no match. Off by "
                "default, since some of these are demo or test organizations."
            ),
        )
        parser.add_argument(
            "--org-key",
            action="append",
            dest="org_keys",
            help="Only consider this org_key. Repeatable.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Run the backfill and print one line per organization."""

        rows = backfill_keycloak_organizations(
            apply=options["apply"],
            create_missing=options["create_missing"],
            org_keys=options["org_keys"],
        )

        for row in rows:
            if row.action in APPLIED_VERBS:
                verb = (
                    APPLIED_VERBS[row.action]
                    if row.applied
                    else f"would {row.action.value}"
                )
            else:
                verb = row.action.value
            self.stdout.write(f"{row.org_key}\t{verb}\t{row.detail}")

        counts = {
            action: sum(1 for row in rows if row.action == action)
            for action in BackfillAction
        }
        self.stdout.write(
            "\n"
            + ", ".join(f"{action.value}: {count}" for action, count in counts.items())
            + ("" if options["apply"] else " (dry run)")
        )
