"""
Creates a basic courseware about page. This can be for programs or courses.
"""

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management import BaseCommand

from cms.api import create_default_courseware_page
from cms.models import Course, Program
from cms.utils import get_page_editing_url


class Command(BaseCommand):
    """
    Creates a basic about page for the given courseware object.
    """

    help = "Creates a basic draft about page for the given courseware object."

    def get_optional_values_for_courseware_type(self, courseware_type: str) -> dict:
        """
        Returns a dictionary of optional values to include when creating the page,
        based on the type of courseware (Course or Program).
        """
        if courseware_type == "Course":
            # Just some hardcoded example values for demonstration purposes. Might make sense to use faker for some of this or allow selection of values from different presets

            return {
                "price": [
                    (
                        "price_details",
                        {
                            "text": "Three easy payments of 99.99",
                            "link": "https://example.com/pricing",
                        },
                    )
                ],
                "min_weeks": 1,
                "max_weeks": 1,
                "effort": "1-2 hours per week",
                "min_price": 37,
                "max_price": 149,
                "prerequisites": "No prerequisites, other than a willness to learn",
                "about": "In this engineering course, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites.",
                "faq_url": "https://example.com",
                "what_you_learn": "In this engineering course, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites.",
            }
        elif courseware_type == "Program":
            return {}
        return {}

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "courseware_id",
            type=str,
            help="The courseware object to work with (a Course or Program).",
        )

        parser.add_argument(
            "--live", action="store_true", help="Make the page live. (Defaults to not.)"
        )
        parser.add_argument(
            "--include_in_learn_catalog",
            action="store_true",
            help="Make the page included in the Learn catalog; courses-only. (Defaults to not.)",
        )
        parser.add_argument(
            "--ingest_content_files_for_ai",
            action="store_true",
            help="Ingest content files for AI processing; courses-only. (Defaults to not.)",
        )
        parser.add_argument(
            "--include_optional_values",
            action="store_true",
            help="Include more than bare minimum required fields while creating the page. By default these will not be populated",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        include_optional_values = kwargs["include_optional_values"]
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
            optional_kwargs = (
                {}
                if not include_optional_values
                else self.get_optional_values_for_courseware_type(
                    courseware.__class__.__name__
                )
            )
            page = create_default_courseware_page(
                courseware,
                live=kwargs["live"],
                include_in_learn_catalog=kwargs["include_in_learn_catalog"],
                ingest_content_files_for_ai=kwargs["ingest_content_files_for_ai"],
                optional_kwargs=optional_kwargs,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"About page created successfully for {courseware.readable_id}\n"
                    f"Edit page at: {get_page_editing_url(page.id)}"
                )
            )
        except ValidationError as e:
            self.stderr.write(
                self.style.ERROR(
                    f"An error occurred creating the about page for {courseware.readable_id}: {e}"
                )
            )
