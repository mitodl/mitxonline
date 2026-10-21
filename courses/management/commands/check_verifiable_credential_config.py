from django.core.management import BaseCommand

from courses.api import (
    VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA,
    summarize_verifiable_credential_certificate_statuses,
)
from courses.models import (
    Course,
    Program,
)


class Command(BaseCommand):
    """
    Prints status of verifiable credential configuration for certificate pages.
    """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-i",
            "--ids",
            type=str,
            default="",
            help="Comma-separated list of certificate page wagtail object ids to check the verifiable credential status for",
        )
        parser.add_argument(
            "--verbose",
            default=False,
            action="store_true",
            help="Print verbose output",
        )
        parser.add_argument(
            "-r",
            "--readable-ids",
            type=str,
            default="",
            help="Comma-separated list of readable ids for courses or programs to check the verifiable credential status for",
        )

    def get_wagtail_ids_from_readable_ids(self, readable_ids):
        # This is not particularly performant, but at least it's straightforward.
        # The alternative requires jumping through wagtail's data layout, probably overkill for this use case.
        courseware = [
            *Course.objects.filter(readable_id__in=readable_ids).select_related("page"),
            *Program.objects.filter(readable_id__in=readable_ids).select_related(
                "page"
            ),
        ]
        return [obj.certificate_page.id for obj in courseware if obj.certificate_page]

    def handle(self, *args, **options):  # noqa: ARG002
        ids = options["ids"].split(",") if options["ids"] else None
        readable_ids = (
            options["readable_ids"].split(",") if options["readable_ids"] else None
        )
        if readable_ids and ids:
            self.stdout.write(
                self.style.ERROR("Cannot specify both --ids and --readable-ids")
            )
            return

        if readable_ids:
            ids = self.get_wagtail_ids_from_readable_ids(readable_ids)
        verbose = options["verbose"]
        breakdown = summarize_verifiable_credential_certificate_statuses(
            return_objects=False, ids=ids
        )
        self.stdout.write("Certificate statuses:")
        for status, certificates in breakdown.items():
            self.stdout.write(f"{status}: {len(certificates)}")
        # Warn on the specific case of certificates with no criteria, since this is an atypical state and may indicate misconfiguration.
        if breakdown.get(VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA):
            self.stdout.write(
                self.style.WARNING(
                    f"{len(breakdown[VERIFIABLE_CREDENTIAL_STATUS_NO_CRITERIA])} enabled certificates have no criteria and will not have verifiable credentials generated for them."
                )
            )
        if verbose:
            for status in breakdown:
                certificates = breakdown[status]
                for certificate in certificates:
                    self.stdout.write(f"{certificate}: {status}")
