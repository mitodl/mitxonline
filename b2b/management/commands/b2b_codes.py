"""Management command to work with B2B enrollment codes."""

import csv
import json
import logging
from pathlib import Path

from django.core.management import BaseCommand, CommandError
from rich.console import Console
from rich.table import Table

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Operations for B2B enrollment codes."""

    help = "Operations to manage B2B enrollment codes - check validity, create/update, etc."
    operations = [
        "check",
        "generate",
        "validate",
        "expire",
    ]
    output_options = [
        "fancy",
        "csv",
        "json",
    ]

    def _add_b2b_obj_args(self, parser):
        """Add B2B object arguments to the parser."""

        parser.add_argument(
            "--contract",
            help="The contract to manage (either ID or slug).",
            type=str,
        )
        parser.add_argument(
            "--organization",
            "--org",
            help="The organization to pull contracts to manage from (either ID, slug, or UUID).",
            type=str,
        )

    def _handle_output(
        self, output_format, output_data, *, filename=None, table_name="Table"
    ):
        """Handle the output for the check command."""

        if output_format not in ["csv", "json"]:
            # Output using Rich - this goes straight to the console.
            console = Console()
            table = Table(title=table_name)

            for col_name in output_data[0]:
                table.add_column(col_name)

            for row in output_data:
                table.add_row(row.values())

            console.print(table)
            return

        outfile = Path.open(filename, "w+") if filename else self.stdout

        if output_format == "json":
            json.dump(output_data, outfile)
        else:
            writer = csv.DictWriter(outfile, output_data[0].keys())

            writer.writeheader()
            for row in output_data:
                writer.writerow(row)

        if filename:
            outfile.close()
            self.stdout.write(
                self.style.SUCCESS(f"Wrote {output_format} output to {filename}.")
            )

    def handle_output(self):
        """Output code information."""

    def handle_validate(self):
        """Validate and fix enrollment codes."""

    def handle_expire(self):
        """Expire enrollment codes."""

    def add_arguments(self, parser):
        """Add arguments to the command."""

        subparser = parser.add_subparsers(
            title="Operation",
            help="The operation to perform.",
            dest="operation",
        )

        output_parser = subparser.add_parser(
            "output",
            help="Output enrollment codes for a contract or organization.",
        )
        validate_parser = subparser.add_parser(
            "validate",
            help="Validate and fix enrollment codes for a contract or organization.",
            aliases=[
                "fix",
                "check",
            ],
        )
        expire_parser = subparser.add_parser(
            "expire",
            help="Expire enrollment codes for a contract or organization, optionally creating new ones.",
        )

        self._add_b2b_obj_args(output_parser)
        self._add_b2b_obj_args(validate_parser)
        self._add_b2b_obj_args(expire_parser)

        output_parser.add_argument(
            "--format",
            type=str,
            default="fancy",
            choices=self.output_options,
            help="Output format (json, csv, fancy)",
            dest="output_format",
        )
        output_parser.add_argument(
            "--stats",
            action="store_true",
            help="Output statistics about code usage.",
        )
        output_parser.add_argument(
            "--usage",
            action="store_true",
            help="Output redemptions/usage for codes.",
        )

        validate_parser.add_argument(
            "--fix",
            help="Fix the codes - otherwise, this will just tell you if the code set is invalid.",
            action="store_true",
        )

        expire_parser.add_argument(
            "--expire",
            help="Expire the codes without prompting.",
            action="store_true",
        )

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Dispatch the requested subcommand."""

        op = kwargs.pop("operation")

        if op == "output":
            self.handle_output()
        elif op == "validate":
            self.handle_validate()
        elif op == "expire":
            self.handle_expire()
        else:
            msg = f"Invalid subcommand {op}"
            raise CommandError(msg)
