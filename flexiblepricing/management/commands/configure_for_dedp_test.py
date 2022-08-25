import pytest
import pytz
from datetime import date, datetime
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from flexiblepricing.management.commands import configure_for_dedp
from courses.models import Program
from flexiblepricing.models import FlexiblePriceTier
from ecommerce.models import Discount
from ecommerce.factories import DiscountFactory

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("with_existing_records", [False, True])
def test_dedp_setup(with_existing_records):
    """
    Runs the setup command and then makes sure the result is correct.
    This tests specifically a setup where there's no existing DEDP records.
    """
    this_year = date.today().year
    content_type = ContentType.objects.filter(
        app_label="courses", model="program"
    ).first()

    Program.objects.filter(readable_id="program-v1:MITx+DEDP").all().delete()
    Discount.objects.filter(
        discount_code__startswith="DEDP-fa-tier", discount_code__endswith=this_year
    ).all().delete()

    if with_existing_records:
        existing_program = Program(
            readable_id="program-v1:MITx+DEDP", title="A Custom Title"
        )
        existing_program.save()
        existing_discount = DiscountFactory.create(
            discount_code="DEDP-fa-tier1-1999", for_flexible_pricing=True
        )
        existing_tier = FlexiblePriceTier(
            courseware_content_type=content_type,
            courseware_object_id=existing_program.id,
            current=True,
            income_threshold_usd=24129,
            discount=existing_discount,
        )
        existing_tier.save()

    configure_for_dedp.Command().handle()

    assert Program.objects.filter(readable_id="program-v1:MITx+DEDP").exists()

    program = Program.objects.filter(readable_id="program-v1:MITx+DEDP").first()
    discounts_qset = Discount.objects.filter(
        discount_code__startswith="DEDP-fa-tier", discount_code__endswith=this_year
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
