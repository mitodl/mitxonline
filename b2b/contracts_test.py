"""Tests for B2B contract provisioning."""

from decimal import Decimal

import pytest

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import (
    CONTRACT_MEMBERSHIP_AUTO,
    CONTRACT_MEMBERSHIP_CODE,
    CONTRACT_MEMBERSHIP_MANAGED,
)
from b2b.contracts import (
    add_courseware_to_contract,
    create_contract,
    ensure_default_variant,
    expected_enrollment_code_count,
    expire_unused_enrollment_codes,
    remove_courseware_from_contract,
)
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import DiscountContractAttachmentRedemption
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def mocked_edx(mocker):
    """Keep contract run creation and removal away from edX."""

    mocker.patch("b2b.contracts.push_run_dates_to_edx")
    return mocker.patch("openedx.tasks.clone_courserun.delay")


def _source_run():
    """Create a course with a source run contract runs can be cloned from."""

    return CourseRunFactory.create(
        is_source_run=True, language="en", is_primary_language=True
    )


def test_create_contract():
    """A new contract sits under its organization with a default variant set."""

    organization = OrganizationPageFactory.create()

    contract = create_contract(
        organization,
        name="Spring cohort",
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=25,
        enrollment_fixed_price=Decimal("10.00"),
    )

    assert contract.get_parent().specific == organization
    assert contract.organization == organization
    assert contract.title == "Spring cohort"
    assert contract.max_learners == 25
    default_variant = contract.variant_options.get()
    assert default_variant.default_variant is True
    assert default_variant.language == "en"


def test_ensure_default_variant_keeps_existing():
    """A contract that has a default variant set keeps it."""

    contract = ContractPageFactory.create()
    existing = contract.variant_options.get(default_variant=True)

    assert ensure_default_variant(contract) == existing
    assert contract.variant_options.count() == 1


def test_add_course_does_not_rerun(mocked_edx):
    """Adding a course twice leaves one contract run, and queues one clone."""

    contract = ContractPageFactory.create()
    course = _source_run().course

    first = add_courseware_to_contract(contract, course)
    second = add_courseware_to_contract(contract, course)

    assert first.runs_added == 1
    assert second.runs_added == 0
    assert contract.get_course_runs().count() == 1
    mocked_edx.assert_called_once()


def test_add_program():
    """Adding a program creates its courses' runs and links the program."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    for _ in range(2):
        program.add_requirement(_source_run().course)

    added = add_courseware_to_contract(contract, program, skip_edx=True)

    assert added.runs_added == 2
    assert added.courses_without_source_run == 0
    assert list(contract.programs) == [program]


def test_add_run_in_another_contract_is_skipped():
    """A run already in another contract stays there and is reported."""

    run = CourseRunFactory.create()
    other_contract = ContractPageFactory.create()
    run.b2b_contracts.add(other_contract)
    contract = ContractPageFactory.create()

    added = add_courseware_to_contract(contract, run)

    assert added.runs_added == 0
    assert str(other_contract) in added.skipped_reason
    assert not run.b2b_contracts.filter(id=contract.id).exists()


@pytest.mark.parametrize("has_enrollments", [True, False])
def test_remove_course(has_enrollments):
    """
    Removing a course closes its contract runs, and unlinks those nobody has
    enrolled in.
    """

    contract = ContractPageFactory.create()
    course = _source_run().course
    add_courseware_to_contract(contract, course, skip_edx=True)
    [run] = contract.get_course_runs()
    if has_enrollments:
        CourseRunEnrollmentFactory.create(run=run)

    [(removed_run, unlinked)] = remove_courseware_from_contract(contract, course)

    removed_run.refresh_from_db()
    assert unlinked is not has_enrollments
    assert removed_run.live is False
    assert contract.get_course_runs().filter(id=run.id).exists() is has_enrollments
    assert not contract.get_products().exists()


def test_remove_run_outside_contract():
    """A run that is not in the contract is not touched."""

    contract = ContractPageFactory.create()
    run = CourseRunFactory.create(live=True)

    assert remove_courseware_from_contract(contract, run) == []
    run.refresh_from_db()
    assert run.live is True


@pytest.mark.parametrize(
    ("membership_type", "price", "max_learners", "expected"),
    [
        (CONTRACT_MEMBERSHIP_MANAGED, None, 5, 0),
        (CONTRACT_MEMBERSHIP_AUTO, None, None, 0),
        (CONTRACT_MEMBERSHIP_AUTO, Decimal("5.00"), None, 2),
        (CONTRACT_MEMBERSHIP_CODE, None, None, 2),
        (CONTRACT_MEMBERSHIP_CODE, None, 3, 6),
    ],
)
def test_expected_enrollment_code_count(membership_type, price, max_learners, expected):
    """Codes are expected per product, times the seat cap when there is one."""

    contract = ContractPageFactory.create(
        membership_type=membership_type,
        enrollment_fixed_price=price,
        max_learners=max_learners,
    )
    for _ in range(2):
        add_courseware_to_contract(contract, _source_run().course, skip_edx=True)

    assert expected_enrollment_code_count(contract) == expected


@pytest.mark.parametrize("dry_run", [True, False])
def test_expire_unused_enrollment_codes(mocker, dry_run):
    """Unused codes leave the contract; a redeemed one stays."""

    mocker.patch("b2b.tasks.queue_contract_sheet_update_post_save.delay")
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE, max_learners=3
    )
    add_courseware_to_contract(contract, _source_run().course, skip_edx=True)
    ensure_enrollment_codes_exist(contract)
    redeemed = contract.get_discounts().first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=redeemed, contract=contract, user=UserFactory.create()
    )

    expired = expire_unused_enrollment_codes(contract, dry_run=dry_run)

    assert len(expired) == 2
    assert all(deleted for _, deleted in expired)
    assert redeemed.discount_code not in [code for code, _ in expired]
    assert contract.get_discounts().distinct().count() == (3 if dry_run else 1)
