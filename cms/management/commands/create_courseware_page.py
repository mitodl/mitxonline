"""
Creates a basic courseware about page. This can be for programs or courses.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management import BaseCommand

from cms.api import create_default_courseware_page
from cms.models import Course, Program


class Command(BaseCommand):
    """
    Creates a basic about page for the given courseware object.
    """

    help = "Creates a basic draft about page for the given courseware object."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "courseware_id",
            type=str,
            help="The courseware object to work with (a Course or Program).",
        )

        parser.add_argument(
            "--live", action="store_true", help="Make the page live. (Defaults to not.)"
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
            create_default_courseware_page(courseware, kwargs["live"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"About page created successfully for {courseware.readable_id}"
                )
            )
        except ValidationError as e:
            self.stderr.write(
                self.style.ERROR(
                    f"An error occurred creating the about page for {courseware.readable_id}: {e}"
                )
            )
