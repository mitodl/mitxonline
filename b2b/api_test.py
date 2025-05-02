"""Tests for B2B API functions."""

import faker
import pytest
import pytz
from django.conf import settings
from mitol.common.utils import now_in_utc

from b2b import factories
from b2b.api import create_contract_run
from b2b.constants import B2B_RUN_TAG_FORMAT
from courses.factories import CourseFactory
from main.utils import date_to_datetime

FAKE = faker.Factory.create()
pytestmark = [
    pytest.mark.django_db,
]


@pytest.mark.parametrize(
    (
        "has_start",
        "has_end",
    ),
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_create_single_course_run(mocker, has_start, has_end):
    """Test that a single course run is created correctly for a contract."""

    now_time = now_in_utc()
    mocker.patch("b2b.api.now_in_utc", return_value=now_time)

    contract = factories.ContractPageFactory(
        contract_start=FAKE.past_datetime(tzinfo=pytz.timezone(settings.TIME_ZONE))
        if has_start
        else None,
        contract_end=FAKE.future_datetime(tzinfo=pytz.timezone(settings.TIME_ZONE))
        if has_end
        else None,
    )
    course = CourseFactory()
    run, product = create_contract_run(contract, course)

    assert run.course == course
    assert run.run_tag == B2B_RUN_TAG_FORMAT.format(
        org_id=contract.organization.id, contract_id=contract.id
    )
    assert run.b2b_contract == contract

    if has_start:
        assertable_start = date_to_datetime(contract.contract_start, settings.TIME_ZONE)
    else:
        assertable_start = now_time
    assert run.start_date == assertable_start
    assert run.enrollment_start == assertable_start
    assert run.certificate_available_date == assertable_start

    if has_end:
        assert run.end_date == date_to_datetime(
            contract.contract_end, settings.TIME_ZONE
        )
        assert run.enrollment_end == date_to_datetime(
            contract.contract_end, settings.TIME_ZONE
        )
    else:
        assert run.end_date is None
        assert run.enrollment_end is None

    assert product.purchasable_object == run
