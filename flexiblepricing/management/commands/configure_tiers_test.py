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
from flexiblepricing.management.commands import configure_tiers
from flexiblepricing.models import FlexiblePriceTier

pytestmark = [pytest.mark.django_db]

FAKE = faker.Factory.create()


@pytest.mark.parametrize(
    "with_existing_records, as_dedp",
    [[False, True], [False, False], [True, True], [True, False]],
)
def test_program_tier_setup(with_existing_records, as_dedp):
    """
    Runs the configure command for a program and makes sure everything gets created.
    This tests specifically a setup where there's no existing DEDP records.
    If as_dedp is specified, this will use DEDP-specific values.
    """
    this_year = date.today().year
    content_type = ContentType.objects.filter(
        app_label="courses", model="program"
    ).first()

    readable_id = (
        "program-v1:MITx+DEDP" if as_dedp else fuzzy.FuzzyText(length=10).fuzz()
    )
    discount_code_abbrev = "DEDP" if as_dedp else fuzzy.FuzzyText(length=4).fuzz()
    program_title = FAKE.sentence(nb_words=3)

    Program.objects.filter(readable_id=readable_id).all().delete()
    Discount.objects.filter(
        discount_code__startswith=f"{discount_code_abbrev}-fa-tier",
        discount_code__endswith=this_year,
    ).all().delete()

    if with_existing_records:
        existing_program = Program(readable_id=readable_id, title=program_title)
        existing_program.save()
        existing_discount = DiscountFactory.create(
            discount_code=f"{discount_code_abbrev}-fa-tier1-1999",
            payment_type=PAYMENT_TYPE_FINANCIAL_ASSISTANCE,
        )
        existing_tier = FlexiblePriceTier(
            courseware_content_type=content_type,
            courseware_object_id=existing_program.id,
            current=True,
            income_threshold_usd=fuzzy.FuzzyInteger(0, 500).fuzz(),
            discount=existing_discount,
        )
        existing_tier.save()

    if as_dedp:
        configure_tiers.Command().handle()
    else:
        output = StringIO()
        call_command(
            "configure_tiers",
            program=readable_id,
            program_abbrev=discount_code_abbrev,
            program_name=program_title,
            stdout=output,
        )

    assert Program.objects.filter(readable_id=readable_id).exists()

    program = Program.objects.filter(readable_id=readable_id).first()
    discounts_qset = Discount.objects.filter(
        discount_code__startswith=f"{discount_code_abbrev}-fa-tier",
        discount_code__endswith=this_year,
    )

    assert discounts_qset.count() == 4

    assert (
        FlexiblePriceTier.objects.filter(
            current=True,
            discount__in=discounts_qset.all(),
            courseware_object_id=program.id,
            courseware_content_type=content_type,
        ).count()
        == 4
    )

    if with_existing_records:
        existing_discount.refresh_from_db()
        existing_tier.refresh_from_db()
        existing_program.refresh_from_db()

        assert program == existing_program
        assert (
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
    this_year = date.today().year
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

        assert (
            existing_discount.expiration_date is not None
            and existing_discount.expiration_date
            < datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        )
        assert existing_tier.current is False
