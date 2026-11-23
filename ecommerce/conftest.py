"""Common fixtures for ecommerce tests"""

from decimal import Decimal

import pytest

from courses.factories import CourseRunFactory
from ecommerce.factories import make_paid_amount_off_offer


@pytest.fixture(autouse=True)
def mocked_hubspot_deal_sync(mocker):
    return mocker.patch("hubspot_sync.task_helpers.sync_hubspot_deal")


@pytest.fixture
def paid_amount_off_source(user):
    """One learner holding a run purchase that funds a paid-amount-off credit."""
    return make_paid_amount_off_offer(user, CourseRunFactory.create())


@pytest.fixture
def taxed_locale(settings):
    """
    Place every user in India, and tax India at 18% VAT.

    Returns the TaxRate.
    """
    from ecommerce.factories import TaxRateFactory  # noqa: PLC0415
    from location.constants import (  # noqa: PLC0415
        LOCATION_FLAG_RULE_MATCH_ANY,
        LOCATION_FLAG_TYPE_TAX,
    )
    from location.factories import LocationFlagFactory  # noqa: PLC0415

    settings.LOCATION_FORCE_COUNTRY = "IN"
    LocationFlagFactory.create(
        flag_type=LOCATION_FLAG_TYPE_TAX,
        determination_rule=LOCATION_FLAG_RULE_MATCH_ANY,
        country_code="IN",
    )
    return TaxRateFactory.create(
        country_code="IN", tax_rate=Decimal(18), tax_rate_name="VAT"
    )
