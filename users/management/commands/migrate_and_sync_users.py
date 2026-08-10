"""
Orchestrate the full edX-to-Keycloak user migration pipeline: backfill edX
data, classify each candidate user by how confident we are in their name
data, sync to Keycloak via SCIM, verify what was actually stored, and report.

This replaces the old two-step manual process (running `migrate_edx_data`,
then an ad hoc SCIM sync script with no field-level visibility) with one
auditable command.
"""

import json

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, call_command
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
            help="Limit the number of users processed (for testing purposes).",
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
            help="Run backfill and classification only; do not sync or write "
            "anything.",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            help="Write the JSON report to this path instead of stdout.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Run the backfill/classify/sync/verify/report pipeline."""
        batch_size = options.get("batch_size") or 250
        limit = options.get("limit")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)
        report_path = options.get("report_path")

        if not options.get("skip_edx_migration", False):
            self.stdout.write("Stage 1: backfilling edX user data...")
            call_command("migrate_edx_data", type="users")
        else:
            self.stdout.write("Stage 1: skipped (--skip-edx-migration).")

        self.stdout.write("Stage 2: classifying sync candidates...")
        candidates = list(
            User.objects.filter(is_active=True)
            .filter(Q(global_id="") | Q(scim_external_id=None))
            .select_related("legal_address")
            .order_by("id")
        )
        if limit is not None:
            candidates = candidates[:limit]

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
                },
                report_path,
            )
            return

        self.stdout.write(f"Stage 3: syncing {len(to_sync)} users to Keycloak...")
        verified, mismatched = [], []
        for start in range(0, len(to_sync), batch_size):
            batch = to_sync[start : start + batch_size]
            states = scim_api.sync_users_to_scim_remote(
                [row["user"] for row in batch]
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

                row["outcome"] = "synced"
                if state.response_body is None:
                    # matched an existing remote user via search, not a fresh
                    # create - nothing to verify against, since nothing new
                    # was sent
                    verified.append(row)
                    continue

                sent_name = row["given_name"], row["family_name"]
                got_name = (
                    state.response_body.get("name", {}).get("givenName"),
                    state.response_body.get("name", {}).get("familyName"),
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
                f"{len(mismatched)} verified-but-mismatched"
            )
        )
        self._write_report(
            {
                "verified": [self._report_row(row) for row in verified],
                "blocked": [self._report_row(row) for row in blocked],
                "mismatched": [self._report_row(row) for row in mismatched],
            },
            report_path,
        )

    def _classify(self, candidates, *, force):
        """Split candidates into (to_sync, blocked) using LearnUserAdapter's
        _resolve_name() tiers, purely for classification/reporting - this
        never writes to legal_address.
        """
        to_sync, blocked = [], []
        for user in candidates:
            adapter = LearnUserAdapter(user)
            given_name, family_name = adapter._resolve_name()  # noqa: SLF001
            legal_address_complete = bool(
                user.legal_address.first_name and user.legal_address.last_name
            )
            row = {
                "user": user,
                "given_name": given_name,
                "family_name": family_name,
                "tier": (
                    "legal_address"
                    if legal_address_complete
                    else ("split_name" if given_name or family_name else "none")
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
