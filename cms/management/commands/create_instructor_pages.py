import sys
import uuid

import faker
import requests
from django.core.files.base import ContentFile
from django.core.management import BaseCommand
from wagtail.images.models import Image

from cms.models import (
    InstructorIndexPage,
    InstructorPage,
    InstructorPageLink,
)
from courses.models import Course, Program


class Command(BaseCommand):
    """
    Creates an instructor page in Wagtail. Optionally, links it to a course or program
    Note that if you have been manually editing CMS content and get an error:
    AttributeError: 'NoneType' object has no attribute '_inc_path'
    You may need to run `./manage.py fixtree --full` to get wagtail into a good state
    """

    help = "Creates an instructor page."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--fake",
            action="store_true",
            default=False,
            help="If true, generate fake data instead of real data.",
        )
        parser.add_argument(
            "--readable-ids",
            type=str,
            default="",
            help="The course to link the instructor to",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=None,
            help="The name of the instructor",
        )
        parser.add_argument(
            "--title",
            type=str,
            default=None,
            help="The title for the instructor",
        )
        parser.add_argument(
            "--image-url",
            type=str,
            default=None,
            help="Image url for the instructor photo",
        )
        parser.add_argument(
            "--link-instructor-id",
            type=str,
            default="",
            help="If specified, skip creation and only link the instructor with this ID to the course",
        )

    def error(self, message):
        self.stdout.write(self.style.ERROR(message))
        sys.exit(1)

    def save_image_file(self, url, filename):
        response = requests.get(url, timeout=10)
        if response.status_code != 200:  # noqa: PLR2004
            self.error(f"Could not download image from {url}")
        image_file = ContentFile(response.content, name=filename)
        instructor_image = Image(title=filename, file=image_file)
        instructor_image.save()
        return instructor_image

    def get_instructor_data(
        self, *, use_fake_data=False, name=None, image_url=None, title=None
    ):
        if use_fake_data:
            fake = faker.Faker()
            instructor_name = fake.name()
            url_safe_instructor_name = instructor_name.replace(" ", "_").lower()
            image_url = f"https://placecats.com/{InstructorPage.RECOMMENDED_IMAGE_WIDTH}/{InstructorPage.RECOMMENDED_IMAGE_HEIGHT}"
            instructor_image = self.save_image_file(
                image_url, f"{url_safe_instructor_name}.jpg"
            )
            instructor_payload = {
                "instructor_name": instructor_name,
                "instructor_title": fake.job(),
                "instructor_bio_short": "An experienced instructor in various subjects.",
                "instructor_bio_long": f"{instructor_name} has been teaching for over 10 years in multiple disciplines.",
                "feature_image": instructor_image,
                "title": f"{instructor_name} Profile",
                "slug": f"{url_safe_instructor_name}",
            }
        else:
            # Use passed in values or stable placeholders.
            # Note that there may be collisions, so we'll tack uuids on where appropriate
            instructor_name = name or "John Doe"
            url_safe_instructor_name = {instructor_name.replace(" ", "_").lower()}
            image_url = image_url or "https://learn.mit.edu/images/mit-red.png"
            # This image is completely the wrong size, but it's stable at least.
            instructor_image = self.save_image_file(image_url, url_safe_instructor_name)
            instructor_payload = {
                "instructor_name": instructor_name,
                "instructor_title": title or "Instructor",
                "instructor_bio_short": "This is a short bio",
                "instructor_bio_long": "This is a longer bio for the instructor",
                "feature_image": instructor_image,
                "title": f"{instructor_name} Profile",
                "slug": f"{instructor_name.replace(' ', '-').lower()}-{uuid.uuid4()}",
            }
        return instructor_payload

    def link_instructor_to_course_or_program(self, instructor_page, readable_id):
        courseware_object = Course.objects.filter(readable_id=readable_id).first()

        if not courseware_object:
            courseware_object = Program.objects.filter(readable_id=readable_id).first()

        if not courseware_object:
            self.error(f"Could not find course with id {readable_id}")

        page = courseware_object.page
        if not page:
            self.error(
                f"Course {readable_id} does not have a CMS page to link to. Consider creating one with create_courseware_page and rerunning with ./manage.py create_instructor_pages --link-instructor-id='{instructor_page.id}' --readable-id='{readable_id}'."
            )
        InstructorPageLink(linked_instructor_page=instructor_page, page=page).save()

    def handle(self, *args, **options):  # pylint: disable=unused-argument  # noqa: ARG002
        use_fake_data = options["fake"]
        readable_ids = options["readable_ids"].split(",")
        link_instructor_id = options["link_instructor_id"]
        if link_instructor_id:
            instructor_page = InstructorPage.objects.filter(
                id=link_instructor_id
            ).first()
            if not instructor_page:
                self.error(f"Could not find instructor with id {link_instructor_id}")
        else:
            instructor_index_page = InstructorIndexPage.objects.first()
            instructor_payload = self.get_instructor_data(
                use_fake_data=use_fake_data,
                name=options["name"],
                image_url=options["image_url"],
                title=options["title"],
            )
            instructor_page = InstructorPage(**instructor_payload)
            instructor_index_page.add_child(instance=instructor_page)
            instructor_page.save_revision().publish()

        if readable_ids:
            for readable_id in readable_ids:
                self.link_instructor_to_course_or_program(instructor_page, readable_id)
