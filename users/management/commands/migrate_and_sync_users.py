"""
Orchestrate the full edX-to-Keycloak user migration pipeline: backfill edX
data, classify each candidate user by how confident we are in their name
data, sync to Keycloak via SCIM, verify what was actually stored, and report.

This replaces the old two-step manual process (running `migrate_edx_data`,
then an ad hoc SCIM sync script with no field-level visibility) with one
auditable command.

Stage 1 delegates to `migrate_edx_data --type users` via `call_command()`
rather than reimplementing its Trino/bulk_create logic here - that command
also serves five other unrelated migration types (course_runs, entitlements,
etc.) and owns the Trino schema, so duplicating its logic would mean two
places to keep in sync as that schema changes. This delegation has real
limits worth knowing: `migrate_edx_data`'s "users" type doesn't support
`--dry-run` (only its course_runs/entitlements types do), so this command's
own `--dry-run` cannot make Stage 1 a no-op - it always writes unless
`--skip-edx-migration` is also passed. `--limit` is threaded through, since
that type does respect it.
"""

import json

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError, call_command
from django.db.models import Q
from mitol.scim import api as scim_api

from users.adapters import LearnUserAdapter

User = get_user_model()


class Command(BaseCommand):
    """Orchestrate the edX-backfill-then-SCIM-sync user migration pipeline."""

    help = __doc__

    def add_arguments(self, parser):
        """Define the command's CLI flags."""
        parser.add_argument(
            "--skip-edx-migration",
            action="store_true",
            help="Skip Stage 1 (call_command('migrate_edx_data', type='users')) "
            "if it's already been run separately.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=250,
            help="Number of users per SCIM sync batch (default: 250).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit the number of users processed (for testing purposes). "
            "Also passed through to migrate_edx_data's Trino query in Stage 1, "
            "so a small test run doesn't backfill the entire edX dataset just "
            "to test-sync a handful of users.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sync users with no name data anywhere in mitxonline anyway, "
            "with a blank name.givenName/familyName, instead of blocking them.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run classification only; do not sync to Keycloak. Note this "
            "does NOT make Stage 1 a no-op - migrate_edx_data's own 'users' "
            "migration type doesn't support --dry-run, so it still writes "
            "User/LegalAddress/UserProfile rows unless --skip-edx-migration "
            "is also passed.",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            help="Write the JSON report to this path instead of stdout.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Run the backfill/classify/sync/verify/report pipeline."""
        batch_size = self._get_batch_size(options)
        limit = options.get("limit")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)
        report_path = options.get("report_path")

        if options.get("skip_edx_migration", False):
            self.stdout.write("Stage 1: skipped (--skip-edx-migration).")
        else:
            self._run_edx_backfill(limit)

        self.stdout.write("Stage 2: classifying sync candidates...")
        candidates = self._get_candidates(limit)

        to_sync, blocked = self._classify(candidates, force=force)
        self.stdout.write(
            f"  {len(to_sync)} ready to sync, {len(blocked)} blocked "
            f"(pass --force to sync blocked users anyway with a blank name)."
        )

        if dry_run:
            self.stdout.write("Dry run: stopping before Stage 3 (sync).")
            self._write_report(
                {
                    "to_sync": [self._report_row(row) for row in to_sync],
                    "blocked": [self._report_row(row) for row in blocked],
                    "verified": [],
                    "mismatched": [],
                    "matched_unverified": [],
                },
                report_path,
            )
            return

        self.stdout.write(f"Stage 3: syncing {len(to_sync)} users to Keycloak...")
        verified, mismatched, matched_unverified = [], [], []
        for start in range(0, len(to_sync), batch_size):
            batch = to_sync[start : start + batch_size]
            # sync_users_to_scim_remote is a generator - it does nothing
            # until iterated, and yields once instead of supporting repeat
            # iteration. Materialize it here, bounded to this one batch
            # (batch_size, not the whole to_sync list), rather than at the
            # library level where the full result set could be unbounded.
            states = list(
                scim_api.sync_users_to_scim_remote([row["user"] for row in batch])
            )
            self.stdout.write(
                f"  batch {start // batch_size + 1}: "
                f"{sum(1 for s in states if s.success)}/{len(states)} succeeded"
            )

            self.stdout.write("Stage 4: verifying batch...")
            rows_by_user_id = {row["user"].id: row for row in batch}
            for state in states:
                row = rows_by_user_id[state.user.id]
                if not state.success:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  FAILED user={state.user.email} error={state.error}"
                        )
                    )
                    row["outcome"] = "failed"
                    row["error"] = state.error
                    blocked.append(row)
                    continue

                if state.response_body is None:
                    # matched an existing remote user via search, not a fresh
                    # create - nothing was sent, so there's nothing to check
                    # the current Keycloak name against. Report this
                    # distinctly from a real verification, rather than
                    # counting an unchecked name as confirmed-correct.
                    row["outcome"] = "matched_not_verified"
                    matched_unverified.append(row)
                    continue

                row["outcome"] = "synced"

                sent_name = row["given_name"], row["family_name"]
                # Keycloak may omit "name" entirely, or echo it back as an
                # explicit null, for a user synced with a blank given/family
                # name (exactly the population this command targets) -
                # `.get("name", {})` only covers the omitted case; a present
                # `"name": null` returns None itself, and calling .get() on
                # that would raise AttributeError. Normalize every case to "".
                name_body = state.response_body.get("name") or {}
                got_name = (
                    name_body.get("givenName") or "",
                    name_body.get("familyName") or "",
                )
                if got_name == sent_name:
                    verified.append(row)
                else:
                    row["got_given_name"], row["got_family_name"] = got_name
                    mismatched.append(row)
                    self.stdout.write(
                        self.style.ERROR(
                            f"  MISMATCH user={state.user.email} "
                            f"sent={sent_name} got={got_name}"
                        )
                    )

        self.stdout.write("Stage 5: report")
        self.stdout.write(
            self.style.SUCCESS(
                f"  {len(verified)} synced and verified, "
                f"{len(blocked)} blocked/failed, "
                f"{len(mismatched)} verified-but-mismatched, "
                f"{len(matched_unverified)} matched but not verified"
            )
        )
        self._write_report(
            {
                "verified": [self._report_row(row) for row in verified],
                "matched_unverified": [
                    self._report_row(row) for row in matched_unverified
                ],
                "blocked": [self._report_row(row) for row in blocked],
                "mismatched": [self._report_row(row) for row in mismatched],
            },
            report_path,
        )

    def _run_edx_backfill(self, limit):
        """Run Stage 1 (migrate_edx_data's "users" migration type).

        migrate_edx_data's "users" type doesn't support --dry-run (only
        course_runs/entitlements do) - it always writes, so there's no
        dry_run to thread through here. --limit is threaded through so a
        small test run doesn't backfill the entire edX dataset just to
        test-sync a handful of users.
        """
        self.stdout.write("Stage 1: backfilling edX user data...")
        if limit is not None:
            call_command("migrate_edx_data", type="users", limit=limit)
        else:
            call_command("migrate_edx_data", type="users")

    @staticmethod
    def _get_batch_size(options):
        """Resolve --batch-size, rejecting non-positive values.

        range(0, len(to_sync), batch_size) silently performs zero iterations
        for a non-positive step, which would skip Stage 3 entirely for a
        nonempty to_sync list while the command still reports a "successful"
        run - fail fast instead of producing a misleading result.
        """
        batch_size = options.get("batch_size")
        if batch_size is None:
            batch_size = 250
        if batch_size <= 0:
            msg = f"--batch-size must be a positive integer, got {batch_size}."
            raise CommandError(msg)
        return batch_size

    def _get_candidates(self, limit):
        """Fetch Stage 2's sync candidates with the relations LearnUserAdapter
        needs pre-loaded, then apply --limit.

        LearnUserAdapter.__init__ touches user_profile and the openedx_user
        cached_property on every instantiation (see _classify below) -
        user_profile is a real OneToOneField, so select_related covers it,
        but openedx_user is backed by self.openedx_users.first(), which
        select_related can't target (openedx_users is the real FK) and
        prefetch_related alone doesn't help either, since .first() re-queries
        instead of using the prefetch cache. So prime the cached_property's
        cache manually from the bulk prefetch below, rather than paying one
        extra query per candidate.
        """
        queryset = (
            User.objects.filter(is_active=True)
            .filter(
                Q(global_id="") | Q(global_id__isnull=True) | Q(scim_external_id=None)
            )
            .select_related("legal_address", "user_profile")
            .prefetch_related("openedx_users")
            .order_by("id")
        )
        if limit is not None:
            # Slice before evaluating - applying LIMIT in SQL, not fetching
            # and prefetching every unsynced user in the table just to
            # discard all but the first `limit` in Python afterward.
            queryset = queryset[:limit]
        candidates = list(queryset)
        for user in candidates:
            prefetched = list(user.openedx_users.all())
            user.__dict__["openedx_user"] = prefetched[0] if prefetched else None
        return candidates

    def _classify(self, candidates, *, force):
        """Split candidates into (to_sync, blocked) using LearnUserAdapter's
        _resolve_name() tiers, purely for classification/reporting - this
        never writes to legal_address.

        _resolve_name() only ever returns a non-blank (given_name,
        family_name) when legal_address already has both parts - it no
        longer guesses a split from User.name (see users/adapters.py). So a
        user with only a full name on file (the common edxorg-migration
        case) always resolves to ("", "") here, same as a user with no name
        data at all. Tier is therefore based on User.name directly, not on
        given_name/family_name: a full name we can't split is still safe to
        sync by default, since LearnUserAdapter.to_dict() sends it outbound
        via the "fullName" attribute regardless of the given/family split.
        """
        to_sync, blocked = [], []
        for user in candidates:
            adapter = LearnUserAdapter(user)
            given_name, family_name = adapter._resolve_name()  # noqa: SLF001
            legal_address_complete = bool(
                user.legal_address.first_name and user.legal_address.last_name
            )
            full_name = (user.name or "").strip()
            row = {
                "user": user,
                "given_name": given_name,
                "family_name": family_name,
                "tier": (
                    "legal_address"
                    if legal_address_complete
                    else ("full_name_only" if full_name else "none")
                ),
            }
            if row["tier"] == "none" and not force:
                row["outcome"] = "blocked"
                blocked.append(row)
            else:
                if row["tier"] == "none":
                    row["outcome"] = "forced-blank-name"
                to_sync.append(row)
        return to_sync, blocked

    @staticmethod
    def _report_row(row):
        return {
            "user_id": row["user"].id,
            "email": row["user"].email,
            "tier": row["tier"],
            "given_name": row["given_name"],
            "family_name": row["family_name"],
            "outcome": row.get("outcome"),
            "error": row.get("error"),
            "got_given_name": row.get("got_given_name"),
            "got_family_name": row.get("got_family_name"),
        }

    def _write_report(self, report, report_path):
        output = json.dumps(report, indent=2, default=str)
        if report_path:
            with open(report_path, "w") as f:  # noqa: PTH123
                f.write(output)
            self.stdout.write(f"Report written to {report_path}")
        else:
            self.stdout.write(output)
