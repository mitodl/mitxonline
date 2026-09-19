"""
Find and (optionally) fix Keycloak users whose firstName/lastName/fullName
are blank or stale, for users that were already synced before the
LearnUserAdapter fix that adds name.givenName/name.familyName/fullName to
the outbound SCIM payload.

sync_users_to_scim_remote only ever creates users that don't already exist
remotely - it has no update/PATCH path - so re-running the sync does nothing
for users that are already in Keycloak. This command talks to Keycloak's
Admin API directly instead, bypassing SCIM entirely.

firstName/lastName are only ever patched when legal_address has both parts
on file - that's the only source LearnUserAdapter trusts for a split name.
Most edxorg-migrated users don't have that; for them, only the fullName
custom attribute (fed by User.name) is patched, leaving Keycloak's existing
firstName/lastName untouched rather than guessing.

Default mode is dry-run: report every candidate and what would change,
write nothing. Pass --apply to actually patch Keycloak.

--fill-only narrows the candidates to users whose Keycloak fullName is empty,
and patches only fullName for them. Nothing Keycloak already holds is
overwritten: users whose fullName or firstName/lastName merely differ from
mitxonline are counted as skipped instead, pending a decision on which side
is authoritative.
"""

import json

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from b2b.keycloak_admin_api import bootstrap_client
from b2b.keycloak_admin_dataclasses import UserRepresentation
from users.adapters import LearnUserAdapter

User = get_user_model()

PAGE_SIZE = 100


def _keycloak_full_name(keycloak_user):
    """Read the "fullName" custom attribute off a Keycloak UserRepresentation.

    Keycloak stores custom attributes as ``{name: [values]}``; ``attributes``
    itself may be None, and the list may be empty or hold an empty string.
    """
    values = (keycloak_user.attributes or {}).get("fullName") or []
    return (values[0] or "").strip() if values else ""


class Command(BaseCommand):
    """Find and (optionally) patch already-migrated Keycloak users' names."""

    help = __doc__

    def add_arguments(self, parser):
        """Define the command's CLI flags."""
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually PUT the corrected firstName/lastName/fullName to "
            "Keycloak. Without this flag, only reports what would change.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Cap how many users get patched in a single --apply run. "
            "Ignored in dry-run mode (the report always covers everyone).",
        )
        parser.add_argument(
            "--fill-only",
            action="store_true",
            help="Only fill an empty Keycloak fullName, and patch nothing "
            "else. Users whose names differ but aren't blank are counted as "
            "skipped, not patched.",
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
        fill_only = options.get("fill_only", False)
        report_path = options.get("report_path")

        client = bootstrap_client(verify_realm=True)

        patched, would_patch, unpatchable = [], [], []
        up_to_date_count = 0
        skipped_by_fill_only_count = 0
        patch_count = 0

        for keycloak_user, user in self._paired_users(client):
            adapter = LearnUserAdapter(user)
            given_name, family_name = adapter._resolve_name()  # noqa: SLF001
            have_split_name = bool(given_name)
            full_name = (user.name or "").strip()

            if not have_split_name and not full_name:
                unpatchable.append(
                    self._row(keycloak_user, user, given_name, family_name, full_name)
                )
                continue

            current_full_name = _keycloak_full_name(keycloak_user)
            names_match = not have_split_name or (
                (keycloak_user.first_name or "") == given_name
                and (keycloak_user.last_name or "") == family_name
            )
            full_name_matches = not full_name or current_full_name == full_name

            if names_match and full_name_matches:
                up_to_date_count += 1
                continue

            if fill_only:
                if not full_name or current_full_name:
                    skipped_by_fill_only_count += 1
                    continue
                # Only fullName is written in this mode, so the split name
                # must not be patched, verified, or shown in the report row.
                have_split_name = False
                given_name = family_name = ""

            row = self._row(keycloak_user, user, given_name, family_name, full_name)

            if not apply_changes:
                would_patch.append(row)
                continue

            if limit is not None and patch_count >= limit:
                would_patch.append(row)
                continue

            row["verified"] = self._patch_user(
                client,
                keycloak_user,
                (given_name, family_name) if have_split_name else None,
                full_name,
            )
            patched.append(row)
            patch_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(patched)} patched, {len(would_patch)} would-patch, "
                f"{len(unpatchable)} unpatchable (no name data anywhere), "
                f"{up_to_date_count} already up to date"
                + (
                    f", {skipped_by_fill_only_count} skipped by --fill-only "
                    "(fullName already set, or no mitxonline name to fill it)"
                    if fill_only
                    else ""
                )
            )
        )
        # Up-to-date users are counted, not listed: a row for each would grow
        # with the whole realm rather than with the users that need a fix.
        # would_patch and unpatchable still hold a row per user until the end.
        report = {
            "patched": patched,
            "would_patch": would_patch,
            "unpatchable": unpatchable,
            "up_to_date_count": up_to_date_count,
        }
        if fill_only:
            report["skipped_by_fill_only_count"] = skipped_by_fill_only_count
        self._write_report(report, report_path)

    @staticmethod
    def _patch_user(client, keycloak_user, split_name, full_name):
        """PUT the resolved names to Keycloak, then re-fetch to verify them.

        :param split_name: ``(given_name, family_name)`` to write to
            firstName/lastName, or None to leave them untouched.
        :param full_name: value for the fullName attribute, or "" to leave it.
        :returns: whether the re-fetched user carries every value written,
            and every root field this didn't write is unchanged.
        :rtype: bool
        """
        patch = {}
        if split_name:
            # client.save() PUTs this dict as raw JSON straight to
            # Keycloak's admin REST API - it never goes through
            # UserRepresentation, so these must be Keycloak's actual
            # wire-format field names (firstName/lastName), not the
            # pydantic model's snake_case attribute names.
            patch["firstName"], patch["lastName"] = split_name
        if full_name:
            attributes = dict(keycloak_user.attributes or {})
            attributes["fullName"] = [full_name]
            patch["attributes"] = attributes

        client.save(f"users/{keycloak_user.id}", patch)
        # verify - don't just trust a 2xx
        refetched = client.retrieve(f"users/{keycloak_user.id}", UserRepresentation)
        if split_name:
            names_verified = (refetched.first_name or "") == split_name[0] and (
                refetched.last_name or ""
            ) == split_name[1]
        else:
            # A PUT without firstName/lastName must leave them alone; check
            # rather than assume, since a fill-only run sends ~360k of these.
            names_verified = (refetched.first_name or "") == (
                keycloak_user.first_name or ""
            ) and (refetched.last_name or "") == (keycloak_user.last_name or "")
        email_unchanged = (refetched.email or "") == (keycloak_user.email or "")
        full_name_verified = (
            not full_name or _keycloak_full_name(refetched) == full_name
        )
        return names_verified and email_unchanged and full_name_verified

    def _paired_users(self, client):
        """Yield (keycloak_user, mitxonline_user) for each Keycloak page.

        mitxonline users are loaded one Keycloak page at a time, so memory
        stays at one page of each rather than every synced user at once.
        """
        for page in self._paginate_keycloak_users(client):
            users_by_scim_id = self._mitxonline_users_by_scim_id(
                [keycloak_user.id for keycloak_user in page]
            )
            for keycloak_user in page:
                user = users_by_scim_id.get(keycloak_user.id)
                if user is not None:  # otherwise not traceable to mitxonline
                    yield keycloak_user, user

    def _mitxonline_users_by_scim_id(self, scim_ids):
        # LearnUserAdapter.__init__ touches user_profile and openedx_user on
        # every instantiation (not just legal_address), so both need covering
        # here or the loop in handle() does 2 extra queries per user.
        # user_profile is a real OneToOneField; openedx_user reads the
        # `openedx_users` relation, which select_related cannot target.
        users = (
            User.objects.filter(is_active=True, scim_external_id__in=scim_ids)
            .select_related("legal_address", "user_profile")
            .prefetch_related("openedx_users")
        )
        return {user.scim_external_id: user for user in users if user.scim_external_id}

    def _paginate_keycloak_users(self, client):
        first = 0
        while True:
            page = client.list("users", UserRepresentation, first=first, max=PAGE_SIZE)
            if not page:
                return
            yield page
            first += PAGE_SIZE

    @staticmethod
    def _row(keycloak_user, user, given_name, family_name, full_name):
        return {
            "keycloak_id": keycloak_user.id,
            "user_id": user.id,
            "email": user.email,
            "keycloak_first_name": keycloak_user.first_name,
            "keycloak_last_name": keycloak_user.last_name,
            "keycloak_full_name": _keycloak_full_name(keycloak_user) or None,
            "resolved_given_name": given_name,
            "resolved_family_name": family_name,
            "resolved_full_name": full_name,
        }

    def _write_report(self, report, report_path):
        output = json.dumps(report, indent=2, default=str)
        if report_path:
            with open(report_path, "w") as f:  # noqa: PTH123
                f.write(output)
            self.stdout.write(f"Report written to {report_path}")
        else:
            self.stdout.write(output)
