"""Tests for report_unpurchased_upgraded_program_enrollments command."""

from io import StringIO

import pytest

from b2b.factories import ContractPageFactory
from b2b.models import ContractProgramItem
from courses.constants import PROGRAM_ENROLLMENT_UPGRADE_MODE
from courses.factories import ProgramEnrollmentFactory, ProgramFactory
from courses.management.commands import (
    report_unpurchased_upgraded_program_enrollments,
)
from courses.models import PaidProgram
from ecommerce.factories import OrderFactory
from ecommerce.models import OrderStatus
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE

pytestmark = [pytest.mark.django_db]


def _run_command(*, list_rows=False):
    out = StringIO()
    command = report_unpurchased_upgraded_program_enrollments.Command(stdout=out)
    command.handle(list=list_rows)
    return out.getvalue()


def _upgraded_enrollment(program, **kwargs):
    return ProgramEnrollmentFactory.create(
        program=program, enrollment_mode=PROGRAM_ENROLLMENT_UPGRADE_MODE, **kwargs
    )


def test_report_unpurchased_upgraded_program_enrollments():
    """Only upgraded enrollments with no purchase or contract behind them are reported."""
    program = ProgramFactory.create()

    unbacked = _upgraded_enrollment(program)
    unbacked_inactive = _upgraded_enrollment(program, active=False)

    # Audit enrollments aren't upgraded, so they're not reported
    ProgramEnrollmentFactory.create(
        program=program, enrollment_mode=EDX_ENROLLMENT_AUDIT_MODE
    )

    # A fulfilled purchase backs the enrollment
    purchased = _upgraded_enrollment(program)
    PaidProgram.objects.create(
        user=purchased.user,
        program=program,
        order=OrderFactory.create(
            purchaser=purchased.user, state=OrderStatus.FULFILLED
        ),
    )

    # An unfulfilled purchase doesn't
    pending = _upgraded_enrollment(program)
    PaidProgram.objects.create(
        user=pending.user,
        program=program,
        order=OrderFactory.create(purchaser=pending.user, state=OrderStatus.PENDING),
    )

    # Nor does a contract that doesn't include the program
    contract = ContractPageFactory.create()
    wrong_contract = _upgraded_enrollment(program)
    wrong_contract.user.b2b_contracts.add(contract)

    # A contract on the enrollment, or a contract with the program that the
    # learner belongs to, backs the enrollment
    _upgraded_enrollment(program, b2b_contract=contract)
    program_contract = ContractPageFactory.create()
    ContractProgramItem(contract=program_contract, program=program).save(
        skip_run_creation=True
    )
    contract_member = _upgraded_enrollment(program)
    contract_member.user.b2b_contracts.add(program_contract)

    report = report_unpurchased_upgraded_program_enrollments
    reported = set(
        report.get_unpurchased_upgraded_program_enrollments().values_list(
            "id", flat=True
        )
    )
    assert reported == {
        unbacked.id,
        unbacked_inactive.id,
        pending.id,
        wrong_contract.id,
    }

    output = _run_command(list_rows=True)
    assert f"{program.readable_id}: 4" in output
    assert "4 upgraded program enrollments across 1 programs" in output
    assert f"{unbacked.id},{unbacked.user_id},{program.readable_id},True," in output
    # Learner PII stays out of the report
    assert unbacked.user.email not in output
