from argparse import RawTextHelpFormatter

from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand, CommandError

from courses.models import CourseRun, Program
from ecommerce.models import Product
import reversion


class Command(BaseCommand):
    """
    Create products for all the course runs in a program with standard price.
    The default behavior is to create "inactive" product for each of DEDP courses with price $1000.
    Unless specifying --active, running it more than once with default argument will create duplicated 'inactive' products
    """

    help = """
    Create products for each of course runs in a program with standard price:


    For creating 'inactive' products for DEDP courses with price $1000:
    run `./manage.py create_product_for_program_courses`


    For creating 'active' products for DEDP courses with price $1000:
    run `./manage.py create_product_for_program_courses --active`


    For creating 'active' products for program courses with price $2000:
    run `./manage.py create_product_for_program_courses --active --program program-v1:MITx+TEST --price 2000`
    """

    PROGRAM_READABLE_ID = "program-v1:MITx+DEDP"
    PRODUCT_PRICE = "1000"

    def create_parser(self, prog_name, subcommand):  # pylint: disable=arguments-differ
        """
        create parser to add new line in help text.
        """
        parser = super().create_parser(prog_name, subcommand)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--program",
            type=str,
            help="The readable id of the program - e.g. program-v1:MITx+DEDP",
            nargs="?",
            default=self.PROGRAM_READABLE_ID,
        )

        parser.add_argument(
            "--price",
            type=str,
            help="The standard price for each of the program courses. Default price is 1000",
            nargs="?",
            default=self.PRODUCT_PRICE,
        )

        parser.add_argument(
            "--active",
            action="store_true",
            help="Create 'active' product. Default is 'inactive'",
        )

    def handle(self, *args, **options):
        program_readable_id = options["program"]
        price = options["price"]
        active = True if options["active"] else False

        program = Program.objects.filter(readable_id=program_readable_id).first()
        if program is None:
            raise CommandError(
                f"Could not find program with readable_id - {self.PROGRAM_READABLE_ID}"
            )

        course_ids = program.courses.values_list("id", flat=True)
        course_runs = CourseRun.objects.select_related("course").filter(
            course_id__in=course_ids
        )

        self.stdout.write(
            f"Creating product for each course in {program_readable_id} with price={price} and active={active})"
        )

        course_run_content_type = ContentType.objects.get(
            app_label="courses", model="courserun"
        )
        for course_run in course_runs:
            with reversion.create_revision():
                product, created = Product.objects.get_or_create(
                    object_id=course_run.id,
                    content_type=course_run_content_type,
                    is_active=active,
                    defaults={"description": course_run.readable_id, "price": price},
                )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created product for course run {course_run.readable_id}"
                    )
                )
            else:
                self.stdout.write(
                    f"Active product for course run - {course_run.readable_id} already exists - Skipping."
                )

        self.stdout.write(self.style.SUCCESS(f"Done!"))
