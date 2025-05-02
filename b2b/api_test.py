"""Tests for B2B API functions."""

import pytest

from b2b import factories
from b2b.api import create_contract_run
from b2b.constants import B2B_RUN_TAG_FORMAT
from courses.factories import CourseFactory

pytestmark = [
    pytest.mark.django_db,
]


def test_create_single_course_run():
    """Test that a single course run is created correctly for a contract."""

    contract = factories.ContractPageFactory()
    course = CourseFactory()
    run, product = create_contract_run(contract, course)

    assert run.course == course
    assert run.start_date == contract.start_date
    assert run.end_date == contract.end_date
    assert run.certificate_available_date == contract.start_date
    assert run.run_tag == B2B_RUN_TAG_FORMAT.format(
        org_id=contract.organization.id, contract_id=contract.id
    )
    assert run.b2b_contract == contract
    assert product.course_run == run
