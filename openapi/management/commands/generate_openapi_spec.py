"""
Management command to generate OpenAPI specs from our APIs.
"""

from pathlib import Path

from django.conf import settings
from django.core import management
from django.core.management import BaseCommand


class Command(BaseCommand):
    """Generate OpenAPI specs for our APIs."""

    help = "Generate OpenAPI specs for our APIs."

    def add_arguments(self, parser):
        """Add arguments to the command"""

        parser.add_argument(
            "--directory",
            dest="directory",
            default="openapi/specs/",
            help="Directory into which output is written",
        )
        parser.add_argument(
            "--fail-on-warn",
            dest="fail-on-warn",
            action="store_true",
            default=False,
            help="Fail the command if there are any warnings",
        )
        parser.add_argument(
            "--only-version",
            dest="only_version",
            help="Only generate the specified version",
        )

        super().add_arguments(parser)

    def handle(self, **options):
        """Run the command"""

        directory = options["directory"]
        versions = (
            [options["only_version"]]
            if "only_version" in options
            and options["only_version"] in settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
            else settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
        )

        for version in versions:
            filename = version + ".yaml"
            filepath = Path(directory) / filename
            management.call_command(
                "spectacular",
                urlconf="main.urls",
                file=filepath,
                validate=True,
                api_version=version,
                fail_on_warn=options["fail-on-warn"],
            )
