"""
Generates enrollment (discount) codes for legacy users. 

This is for learners that have paid for a course but aren't enrolled in a 
course run with a verified enrollment. The list is generated outside this 
command and is passed to it as a CSV file. The format of the file is:

```
learner email,course readable id or course readable id or micromasters course ID
```

and this command will generate single-use per-user discounts for each learner
and course combination (if a product exists for it). The course must be 
available for enrollment and must also have a product associated with it. 
"""
from django.core.management import BaseCommand
import csv
import uuid
from django.db import transaction

from courses.models import CourseRun, Course
from ecommerce.models import Discount, DiscountProduct, UserDiscount
from ecommerce.constants import REDEMPTION_TYPE_ONE_TIME, DISCOUNT_TYPE_PERCENT_OFF
from users.models import User
from micromasters_import.models import CourseId


class Command(BaseCommand):
    """
    Generates enrollment codes for legacy paid learners
    """

    help = "Generates enrollment codes for legacy paid learners"
    CODE_PREFIX = "MM-prepaid-"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "input_file",
            type=str,
            help="Input file. See documentation for file format.",
        )
        parser.add_argument(
            "output_file", type=str, help="File to write the results to."
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        output_codes = []

        with open(kwargs["input_file"], newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=",", quotechar="\\")

            for row in reader:
                user = User.objects.filter(email=row[0]).first()

                if user is None:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Can't find account for user {row[0]}, skipping row"
                        )
                    )
                    continue

                try:
                    mmid = int(row[1])
                    mapped_course = CourseId.objects.filter(
                        micromasters_id=mmid
                    ).first()

                    if mapped_course is None:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Can't find mapped MicroMasters course for {mmid}, skipping row"
                            )
                        )
                        continue

                    courserun = mapped_course.course.first_unexpired_run
                except:
                    courserun = CourseRun.objects.filter(courseware_id=row[1]).first()

                    if courserun is None:
                        course = Course.objects.filter(readable_id=row[1]).first()
                        courserun = (
                            course.first_unexpired_run if course is not None else None
                        )

                        if courserun is None:
                            self.stderr.write(
                                self.style.ERROR(
                                    f"Can't find courserun or course for {row[1]}, skipping row"
                                )
                            )
                            continue

                try:
                    with transaction.atomic():
                        generated_uuid = uuid.uuid4()
                        code = f"{self.CODE_PREFIX}{generated_uuid}"

                        discount = Discount.objects.create(
                            amount=100,
                            discount_type=DISCOUNT_TYPE_PERCENT_OFF,
                            redemption_type=REDEMPTION_TYPE_ONE_TIME,
                            discount_code=code,
                            for_flexible_pricing=False,
                        )

                        DiscountProduct.objects.create(
                            discount=discount,
                            product=courserun.products.filter(is_active=True).first(),
                        )

                        UserDiscount.objects.create(discount=discount, user=user)

                        output_codes.append(
                            [
                                user.email,
                                courserun.courseware_id,
                                code,
                            ]
                        )
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"An error occurred creating the discount for {row[0]} in course {row[1]} - maybe there's no product or valid courserun for the course?; skipping: {e}"
                        )
                    )

        with open(kwargs["output_file"], mode="w", newline="") as codefile:
            writer = csv.writer(codefile, delimiter=",", quotechar="\\")

            writer.writerows(output_codes)

        self.stdout.write(
            self.style.SUCCESS(f"Generated {len(output_codes)} enrollment codes.")
        )
