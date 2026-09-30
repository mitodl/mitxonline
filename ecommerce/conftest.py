"""Common fixtures for ecommerce tests"""

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
