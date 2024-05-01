from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from courses.factories import CourseFactory, CourseRunFactory, ProgramFactory
from courses.models import CourseRun
from ecommerce.models import Product

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "program,price,active",  # noqa: PT006
    [
        ("program-v1:MITx+DEDP", "1000", True),
        ("program-v1:MITx+DEDP", "1000", False),
        ("program-v1:MITx+DEDP", "900", True),
        ("program-v2:MITx+TEST", "1000", True),
        ("program-v2:MITx+TEST", "1000", False),
        ("program-v2:MITx+TEST", "900", True),
    ],
)
def test_create_product_for_program_courses_command(program, price, active):
    """
    Tests for create_product_for_program_courses command
    """
    course_run_content_type = ContentType.objects.get(
        app_label="courses", model="courserun"
    )
    generated_program = ProgramFactory(readable_id=program)
    generated_program.refresh_from_db()
    course = CourseFactory()
    generated_program.add_requirement(course)
    CourseRunFactory.create(course=course)
    run_ids = CourseRun.objects.filter(course=course).values_list("id", flat=True)

    output = StringIO()
    call_command(
        "create_product_for_program_courses",
        program=program,
        price=price,
        active=active,
        stdout=output,
    )

    generated_product = Product.objects.filter(
        object_id__in=run_ids, price=price, content_type=course_run_content_type
    )

    if active:
        assert generated_product.exists()
        assert generated_product.count() == len(run_ids)
    else:
        # For creating inactive products, calling .exists() will return None
        # because ProductsQuerySet filters out inactive ones
        # so this is just to confirm inactive products are created from the output
        assert "Created product for course run course" in output.getvalue()
