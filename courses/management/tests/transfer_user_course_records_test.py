"""Tests for transfer_user_course_records command."""

import pytest

from courses.constants import PROGRAM_ENROLLMENT_UPGRADE_MODE
from courses.factories import ProgramEnrollmentFactory, ProgramFactory
from courses.management.commands import transfer_user_course_records
from ecommerce.factories import make_purchase
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    ("enrollment_mode", "moves_order"),
    [
        (PROGRAM_ENROLLMENT_UPGRADE_MODE, True),
        (EDX_ENROLLMENT_AUDIT_MODE, False),
    ],
)
def test_verified_orders_program(user, enrollment_mode, moves_order):
    """The program order moves with an upgraded program enrollment, not an audit one."""
    program = ProgramFactory.create()
    enrollment = ProgramEnrollmentFactory.create(
        user=user, program=program, enrollment_mode=enrollment_mode
    )
    line = make_purchase(user, program, 100)

    orders = transfer_user_course_records.Command()._verified_orders(  # noqa: SLF001
        user,
        {"course_run_enrollments": [], "program_enrollments": [enrollment]},
    )

    assert orders == ([line.order] if moves_order else [])
