"""
Creates a basic courseware about page. This can be for programs or courses.
"""

import sys

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management import BaseCommand

from cms.api import create_default_courseware_page
from cms.models import Course, InstructorPage, InstructorPageLink, Program
from cms.utils import get_page_editing_url


class Command(BaseCommand):
    """
    Creates a basic about page for the given courseware object.
    """

    help = "Creates a basic draft about page for the given courseware object."

    def get_optional_values_for_courseware_type(self, courseware_type: type) -> dict:
        """
        Returns a dictionary of optional values to include when creating the page,
        based on the type of courseware (Course or Program).
        """

        # Just some hardcoded example values for demonstration purposes.
        # Might make sense to use faker for some of this or allow selection of values from different presets
        # For now though, this sets up a page which is reasonably complete and can be immediately published
        values = {
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
            "prerequisites": "No prerequisites, other than a willingness to learn",
            "faq_url": "https://example.com",
        }
        if isinstance(courseware_type, Course):
            values["about"] = (
                "In this engineering course, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites."
            )
            values["what_you_learn"] = (
                "In this engineering course, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites.",
            )
        elif isinstance(courseware_type, Program):
            values["about"] = (
                "In this engineering program, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites."
            )
            values["what_you_learn"] = (
                "In this engineering program, we will explore the processing and structure of cellular solids as they are created from polymers, metals, ceramics, glasses and composites.",
            )

        return values

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
        parser.add_argument(
            "--link_to_instructor",
            action="store",
            type=str,
            default=None,
            help="Comma separated list of instructor IDs to link to the courseware page.",
        )

    # Should we make this a mixin for other management commands?
    # Could be nice to encapsulate some commonly used logic, if folks like this.
    def error(self, message):
        self.stdout.write(self.style.ERROR(message))
        sys.exit(1)

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        include_optional_values = kwargs["include_optional_values"]
        link_to_instructor = kwargs["link_to_instructor"]
        try:
            courseware = Course.objects.filter(
                readable_id=kwargs["courseware_id"]
            ).first()

            if courseware is None:
                courseware = Program.objects.filter(
                    readable_id=kwargs["courseware_id"]
                ).get()
        except ObjectDoesNotExist:
            self.error(
                f"Can't find courseware object for {kwargs['courseware_id']}, stopping."
            )

        try:
            optional_kwargs = (
                {}
                if not include_optional_values
                else self.get_optional_values_for_courseware_type(courseware.__class__)
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
            self.error(
                f"An error occurred creating the about page for {courseware.readable_id}: {e}"
            )

        if link_to_instructor:
            instructor_page = InstructorPage.objects.get(id=kwargs["instructor_id"])
            InstructorPageLink(linked_instructor_page=instructor_page, page=page).save()
