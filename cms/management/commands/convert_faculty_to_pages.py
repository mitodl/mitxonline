"""
Grabs faculty member data out of existing Course and Program pages and converts
them to be InstructorPage, then assigns them to the course/program they were in.

If there's no root-level instructor index page, this will also create it.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.utils.text import slugify
from wagtail.images.models import Image

from cms.models import (
    CoursePage,
    HomePage,
    InstructorIndexPage,
    InstructorPage,
    InstructorPageLink,
)
from courses.models import Course, Program


class Command(BaseCommand):
    """
    Migrates faculty data from CoursePage/ProgramPage into InstructorPage.
    """

    help = "Migrates faculty data from CoursePage/ProgramPage into InstructorPage."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--only",
            type=str,
            help="Only process the specified courseware object (a Course or Program). Specify the readable ID.",
            dest="courseware",
        )

        parser.add_argument(
            "--publish",
            action="store_true",
            help="Make the page published. (Defaults to draft.)",
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument  # noqa: ARG002
        try:
            instructor_page_root = InstructorIndexPage.objects.filter(live=True).get()

            self.stdout.write("Using existing instructor index page")
        except Exception:  # noqa: BLE001
            hp = HomePage.objects.first()
            # if it errors here then we're all lost
            instructor_page_root = InstructorIndexPage(title="Instructors")
            hp.add_child(instance=instructor_page_root)
            hp.save()
            instructor_page_root.refresh_from_db()

            self.stdout.write("Created new instructor index page")

        if kwargs["courseware"]:
            try:
                course = Course.objects.filter(readable_id=kwargs["courseware"])

                if course.exists():
                    pages = [course.get().page]
                else:
                    pages = [Program.objects.get(readable_id=kwargs["courseware"]).page]
            except ObjectDoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"Courseware object {kwargs['courseware']} not found."
                    )
                )
                exit(-1)  # noqa: PLR1722
        else:
            pages = CoursePage.objects.all()

        for page in pages:
            ibvalues = [
                block.get_prep_value()["value"] for block in page.faculty_members
            ]

            for block in ibvalues:
                existingcount = InstructorPage.objects.filter(
                    instructor_name__istartswith=block["name"]
                ).count()

                if existingcount > 0:
                    self.stdout.write(
                        f"Found {existingcount} records for {block['name']}"
                    )
                    block["title"] = f"{block['name']} ({(existingcount + 1)})"
                else:
                    block["title"] = block["name"]

                try:
                    featured_image = Image.objects.get(pk=block["image"])
                except Exception:  # noqa: BLE001
                    featured_image = None

                page_framework = {
                    "title": block["title"],
                    "instructor_name": block["name"],
                    "instructor_bio_short": block["name"],
                    "instructor_bio_long": block["description"],
                    "live": kwargs["publish"],
                    "slug": slugify(block["title"]),
                    "feature_image": featured_image,
                    "depth": instructor_page_root.depth + 1,  # this is probably safe
                }

                new_instructor = InstructorPage(**page_framework)

                instructor_page_root.add_child(instance=new_instructor)
                instructor_page_root.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created new page for {new_instructor.instructor_name} - title {new_instructor.title}"
                    )
                )

                new_instructor.refresh_from_db()

                InstructorPageLink.objects.create(
                    linked_instructor_page=new_instructor, page=page
                )

                self.stdout.write(
                    self.style.WARNING(
                        f"Added link to {new_instructor.instructor_name} to {page}"
                    )
                )

            page.faculty_members = None
            page.save()

            self.stdout.write(
                self.style.SUCCESS(f"Cleared old-style faculty members from {page}")
            )
