"""
Creates a basic Financial Assistance form.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management import BaseCommand

from cms.models import Course, Program
from flexiblepricing.api import create_default_flexible_pricing_page


class Command(BaseCommand):
    """
    Creates a basic Financial Assistance form for a given courseware object.
    """

    help = "Creates a basic Financial Assistance form for a given courseware object."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "courseware_id",
            type=str,
            help="The readable ID of the course to work with.",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation of the page (only for a course)",
        )

        parser.add_argument(
            "--slug",
            nargs="?",
            default=None,
            type=str,
            help="Specify a slug for the new page.",
        )
        parser.add_argument(
            "--title",
            nargs="?",
            default=None,
            type=str,
            help="Specify a specific title for the page.",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        try:
            courseware = Course.objects.filter(
                readable_id=kwargs["courseware_id"]
            ).first()

            if courseware is None:
                courseware = Program.objects.filter(
                    readable_id=kwargs["courseware_id"]
                ).get()
        except ObjectDoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"Can't find courseware object for {kwargs['courseware_id']}, stopping."
                )
            )
            return

        try:
            if create_default_flexible_pricing_page(
                courseware,
                True if kwargs["force"] else False,  # noqa: SIM210
                **kwargs,
            ):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created financial assistance form for {courseware.readable_id} successfully."
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Can't create financial assistance form for {courseware.readable_id}."
                    )
                )
        except ValidationError as e:
            self.stderr.write(
                self.style.ERROR(
                    f"Can't create financial assistance form for {courseware.readable_id} - perhaps the slug is in use already?"
                )
            )
            self.stderr.write(self.style.ERROR(e))
