"""
Management command to create Orders for CourseRunEnrollments which were created in the past
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from reversion.models import Version

from courses.models import CourseRun, CourseRunEnrollment
from ecommerce.models import Order, PendingOrder, Product
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE


class Command(BaseCommand):
    """
    Create Orders for each audit CourseRunEnrollment as long as there is a Product associated with the CourseRun.
    """

    def handle(self, *args, **options):  # noqa: ARG002
        course_run_enrollments = CourseRunEnrollment.objects.filter(
            enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE
        )
        for course_run_enrollment in course_run_enrollments:
            product = Product.objects.filter(
                object_id=course_run_enrollment.run.id,
                content_type=ContentType.objects.get_for_model(CourseRun),
            ).first()
            if product is None:
                self.stdout.write(
                    f"No product found for that course with courseware_id {course_run_enrollment.run.id} \n"
                )
            else:
                product_version = Version.objects.get_for_object(product).first()
                product_object_id = product.object_id
                product_content_type = product.content_type_id
                existing_fulfilled_order = Order.objects.filter(
                    state__in=[Order.STATE.FULFILLED, Order.STATE.PENDING],
                    purchaser=course_run_enrollment.user,
                    lines__purchased_object_id=product_object_id,
                    lines__purchased_content_type_id=product_content_type,
                    lines__product_version=product_version,
                )
                if not existing_fulfilled_order:
                    # Create PendingOrder
                    PendingOrder.create_from_product(
                        product, course_run_enrollment.user
                    )
        self.stdout.write("'sync_db_to_hubspot --deals create' should be run next. \n")
