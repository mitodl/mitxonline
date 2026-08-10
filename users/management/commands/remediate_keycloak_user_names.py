"""
Find and (optionally) fix Keycloak users whose firstName/lastName are blank
or stale, for users that were already synced before the LearnUserAdapter fix
that adds name.givenName/name.familyName to the outbound SCIM payload.

sync_users_to_scim_remote only ever creates users that don't already exist
remotely - it has no update/PATCH path - so re-running the sync does nothing
for users that are already in Keycloak. This command talks to Keycloak's
Admin API directly instead, bypassing SCIM entirely.

Default mode is dry-run: report every candidate and what would change,
write nothing. Pass --apply to actually patch Keycloak.
"""

import json

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from b2b.keycloak_admin_api import bootstrap_client
from b2b.keycloak_admin_dataclasses import UserRepresentation
from users.adapters import LearnUserAdapter

User = get_user_model()

PAGE_SIZE = 100


class Command(BaseCommand):
    """Find and (optionally) patch already-migrated Keycloak users' names."""

    help = __doc__

    def add_arguments(self, parser):
        """Define the command's CLI flags."""
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually PUT the corrected firstName/lastName to Keycloak. "
            "Without this flag, only reports what would change.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Cap how many users get patched in a single --apply run. "
            "Ignored in dry-run mode (the report always covers everyone).",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            help="Write the JSON report to this path instead of stdout.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Paginate Keycloak users, resolve the correct name, patch or report."""
        apply_changes = options.get("apply", False)
        limit = options.get("limit")
        report_path = options.get("report_path")

        client = bootstrap_client(verify_realm=True)

        mitxonline_users_by_scim_id = self._mitxonline_users_by_scim_id()

        patched, would_patch, unpatchable, up_to_date = [], [], [], []
        patch_count = 0

        for keycloak_user in self._paginate_keycloak_users(client):
            user = mitxonline_users_by_scim_id.get(keycloak_user.id)
            if user is None:
                continue  # not a user we can trace back to mitxonline

            adapter = LearnUserAdapter(user)
            given_name, family_name = adapter._resolve_name()  # noqa: SLF001

            if not given_name and not family_name:
                unpatchable.append(
                    self._row(keycloak_user, user, given_name, family_name)
                )
                continue

            if (
                keycloak_user.firstName == given_name
                and keycloak_user.lastName == family_name
            ):
                up_to_date.append(
                    self._row(keycloak_user, user, given_name, family_name)
                )
                continue

            row = self._row(keycloak_user, user, given_name, family_name)

            if not apply_changes:
                would_patch.append(row)
                continue

            if limit is not None and patch_count >= limit:
                would_patch.append(row)
                continue

            client.save(
                f"users/{keycloak_user.id}",
                {"firstName": given_name, "lastName": family_name},
            )
            # verify - don't just trust a 2xx
            refetched = client.retrieve(
                f"users/{keycloak_user.id}", UserRepresentation
            )
            row["verified"] = (
                refetched.firstName == given_name
                and refetched.lastName == family_name
            )
            patched.append(row)
            patch_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(patched)} patched, {len(would_patch)} would-patch, "
                f"{len(unpatchable)} unpatchable (no name data anywhere), "
                f"{len(up_to_date)} already up to date"
            )
        )
        self._write_report(
            {
                "patched": patched,
                "would_patch": would_patch,
                "unpatchable": unpatchable,
                "up_to_date": up_to_date,
            },
            report_path,
        )

    def _mitxonline_users_by_scim_id(self):
        users = User.objects.filter(is_active=True).exclude(
            scim_external_id__isnull=True
        )
        by_id = {}
        for user in users.select_related("legal_address"):
            if user.scim_external_id:
                by_id[user.scim_external_id] = user
        return by_id

    def _paginate_keycloak_users(self, client):
        first = 0
        while True:
            page = client.list(
                "users", UserRepresentation, first=first, max=PAGE_SIZE
            )
            if not page:
                return
            yield from page
            first += PAGE_SIZE

    @staticmethod
    def _row(keycloak_user, user, given_name, family_name):
        return {
            "keycloak_id": keycloak_user.id,
            "user_id": user.id,
            "email": user.email,
            "keycloak_first_name": keycloak_user.firstName,
            "keycloak_last_name": keycloak_user.lastName,
            "resolved_given_name": given_name,
            "resolved_family_name": family_name,
        }

    def _write_report(self, report, report_path):
        output = json.dumps(report, indent=2, default=str)
        if report_path:
            with open(report_path, "w") as f:  # noqa: PTH123
                f.write(output)
            self.stdout.write(f"Report written to {report_path}")
        else:
            self.stdout.write(output)
