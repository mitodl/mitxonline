from datetime import date, datetime
from io import StringIO

import faker
import pytest
import pytz
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from factory import fuzzy

from courses.factories import CourseFactory
from courses.models import Program
from ecommerce.constants import PAYMENT_TYPE_FINANCIAL_ASSISTANCE
from ecommerce.factories import DiscountFactory
from ecommerce.models import Discount
from flexiblepricing.models import FlexiblePriceTier

pytestmark = [pytest.mark.django_db]

FAKE = faker.Factory.create()


@pytest.mark.parametrize(
    "with_existing_records",
    [False, True],
)
def test_program_tier_setup(with_existing_records):
    """
    Runs the configure command for a program and makes sure everything is created.
    """
    this_year = date.today().year  # noqa: DTZ011
    content_type = ContentType.objects.filter(
        app_label="courses", model="program"
    ).first()

    program_object = Program.objects.create(
        readable_id="program-v1:MITx+DEDP", title=FAKE.sentence(nb_words=3)
    )
    discount_code_abbrev = program_object.readable_id

    Discount.objects.filter(
        discount_code__startswith=f"{discount_code_abbrev}-fa-tier",
        discount_code__endswith=this_year,
    ).all().delete()
    if with_existing_records:
        existing_discount = DiscountFactory.create(
            discount_code=f"{discount_code_abbrev}-fa-tier1-1999",
            payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
        )
        existing_tier = FlexiblePriceTier(
            courseware_content_type=content_type,
            courseware_object_id=program_object.id,
            current=True,
            income_threshold_usd=fuzzy.FuzzyInteger(0, 500).fuzz(),
            discount=existing_discount,
        )
        existing_tier.save()

    output = StringIO()
    call_command(
        "configure_tiers",
        program=program_object.readable_id,
        program_abbrev=discount_code_abbrev,
        stdout=output,
    )
    discounts_qset = Discount.objects.filter(
        discount_code__startswith=f"{discount_code_abbrev}-fa-tier",
        discount_code__endswith=this_year,
    )

    assert discounts_qset.count() == 4

    assert (
        FlexiblePriceTier.objects.filter(
            current=True,
            discount__in=discounts_qset.all(),
            courseware_object_id=program_object.id,
            courseware_content_type=content_type,
        ).count()
        == 4
    )

    if with_existing_records:
        existing_discount.refresh_from_db()
        existing_tier.refresh_from_db()
        assert (  # noqa: PT018
            existing_discount.expiration_date is not None
            and existing_discount.expiration_date
            < datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        )
        assert existing_tier.current is False


@pytest.mark.parametrize(
    "with_existing_records",
    [True, False],
)
def test_course_tier_setup(with_existing_records):
    """
    Runs the setup command for a course and makes sure the tiers are set up.
    """
    this_year = date.today().year  # noqa: DTZ011
    content_type = ContentType.objects.filter(
        app_label="courses", model="course"
    ).first()
    course = CourseFactory.create()

    if with_existing_records:
        existing_discount = DiscountFactory.create(
            discount_code=f"{course.readable_id}-fa-tier1-1999",
            payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
        )
        existing_tier = FlexiblePriceTier(
            courseware_content_type=content_type,
            courseware_object_id=course.id,
            current=True,
            income_threshold_usd=fuzzy.FuzzyInteger(0, 500).fuzz(),
            discount=existing_discount,
        )
        existing_tier.save()

    output = StringIO()
    call_command(
        "configure_tiers",
        course=course.readable_id,
        stdout=output,
    )

    discounts_qset = Discount.objects.filter(
        discount_code__startswith=f"{course.readable_id}-fa-tier",
        discount_code__endswith=this_year,
    )

    assert discounts_qset.count() == 4

    assert (
        FlexiblePriceTier.objects.filter(
            current=True,
            discount__in=discounts_qset.all(),
            courseware_object_id=course.id,
            courseware_content_type=content_type,
        ).count()
        == 4
    )

    if with_existing_records:
        existing_discount.refresh_from_db()
        existing_tier.refresh_from_db()

        assert (  # noqa: PT018
            existing_discount.expiration_date is not None
            and existing_discount.expiration_date
            < datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        )
        assert existing_tier.current is False
