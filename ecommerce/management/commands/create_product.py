"""
Creates a product for the given courseware ID. This only supports course runs
for right now (since we don't really do program runs).
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand

from courses.models import CourseRun
from ecommerce.models import Product


class Command(BaseCommand):
    """
    Creates a product for the given courseware ID.
    """

    help = "Creates a product for the given courseware ID."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "courseware",
            type=str,
            help="The courseware object to make the product for.",
        )

        parser.add_argument("price", type=str, help="The product's price.")

        parser.add_argument(
            "--description",
            "-d",
            nargs="?",
            type=str,
            help="The product's description. Defaults to the courseware object's readable ID.",
            metavar="description",
        )

        parser.add_argument(
            "--inactive", action="store_false", help="Make the product inactive."
        )

    def handle(self, *args, **kwargs):
        try:
            courserun = CourseRun.objects.filter(
                courseware_id=kwargs["courseware"]
            ).get()
        except Exception as e:
            self.stderr.write(f"Could not retrieve {kwargs['courseware']}: {e}")
            exit(-1)

        content_type = ContentType.objects.filter(
            app_label="courses", model="courserun"
        ).get()

        description = courserun.readable_id

        if "description" in kwargs and kwargs["description"] is not None:
            description = kwargs["description"]

        product = Product.objects.create(
            object_id=courserun.id,
            content_type=content_type,
            price=kwargs["price"],
            description=description,
            is_active=kwargs["inactive"],
        )

        self.stdout.write(f"Created product {product}.")
