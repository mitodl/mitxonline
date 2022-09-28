"""
Finds learners who have paid for a currently active course but don't have a 
corresponding verified enrollment in the course. Outputs a CSV file in a format
that is suitable for feeding into `generate_legacy_enrollment_codes`. 
"""
from django.core.management import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

import csv

from mitol.common.utils.datetime import now_in_utc

from courses.models import CourseRunEnrollment, CourseRun
from ecommerce.models import Line, Order


class Command(BaseCommand):
    """
    Finds paid learners without paid enrollments
    """

    help = "Finds paid learners without paid enrollments"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "output_file", type=str, help="File to write the results to."
        )

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        output_codes = []

        active_courseruns = (
            CourseRun.objects.filter(Q(end_date=None) | Q(end_date__gte=now_in_utc()))
            .values_list("id", flat=True)
            .all()
        )
        content_type = ContentType.objects.filter(
            app_label="courses", model="courserun"
        ).first()

        purchased_lines = Line.objects.filter(
            purchased_object_id__in=active_courseruns,
            purchased_content_type=content_type,
            order__state=Order.STATE.FULFILLED,
        ).all()

        for line in purchased_lines:
            if (
                not CourseRunEnrollment.objects.filter(run=line.purchased_object)
                .filter(user=line.order.purchaser)
                .exists()
            ):
                output_codes.append(
                    [
                        line.order.purchaser.email,
                        line.purchased_object.courseware_id,
                    ]
                )

        with open(kwargs["output_file"], mode="w", newline="") as codefile:
            writer = csv.writer(codefile, delimiter=",", quotechar="\\")

            writer.writerows(output_codes)

        self.stdout.write(
            self.style.SUCCESS(f"Found {len(output_codes)} mismatched learners.")
        )
