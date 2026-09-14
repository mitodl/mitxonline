"""Common fixtures for ecommerce tests"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
import reversion
from reversion.models import Version

from courses.factories import CourseRunFactory, ProgramFactory
from ecommerce.factories import (
    PaidAmountOffDiscountFactory,
    ProgramProductFactory,
    make_purchase,
)
from ecommerce.models import DiscountProduct


@pytest.fixture(autouse=True)
def mocked_hubspot_deal_sync(mocker):
    return mocker.patch("hubspot_sync.task_helpers.sync_hubspot_deal")


@pytest.fixture
def paid_amount_off_source(user):
    """
    One learner holding exactly one qualifying source: a $999 program product,
    a $100 paid run of a direct child course, and a paid-amount-off discount
    linked to the program product. Resolving it returns a 100.00 credit, so the
    program prices at 899.00.
    """
    program = ProgramFactory.create()
    run = CourseRunFactory.create()
    program.add_requirement(run.course)
    source_line = make_purchase(user, run, Decimal("100.00"))
    with reversion.create_revision():
        program_product = ProgramProductFactory.create(
            purchasable_object=program, price=Decimal("999.00")
        )
    discount = PaidAmountOffDiscountFactory.create()
    DiscountProduct.objects.create(discount=discount, product=program_product)
    return SimpleNamespace(
        user=user,
        program_product=program_product,
        program_product_version=Version.objects.get_for_object(program_product).first(),
        source_line=source_line,
        discount=discount,
    )
