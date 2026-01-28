"""
Creates a basic courseware about page. This can be for programs or courses.
"""

import sys

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management import BaseCommand

from cms.api import (
    create_default_courseware_page,
    get_optional_placeholder_values_for_courseware_type,
)
from cms.models import Course, InstructorPage, InstructorPageLink, Program
from cms.utils import get_page_editing_url


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
                else get_optional_placeholder_values_for_courseware_type(courseware)
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
            instructor_ids = [
                int(instructor_id)
                for instructor_id in kwargs["link_to_instructor"].split(",")
            ]
            instructor_pages = InstructorPage.objects.filter(id__in=instructor_ids)
            for instructor_page in instructor_pages:
                InstructorPageLink(
                    linked_instructor_page=instructor_page, page=page
                ).save()
