"""Tests for models."""

import faker
import pytest

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import UserOrganization
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


def test_add_program_courses_to_contract(mocker):
    """Test that adding a program to a contract works as expected."""

    mocker.patch("openedx.tasks.clone_courserun.delay")

    program = ProgramFactory.create()
    courseruns = CourseRunFactory.create_batch(3, is_source_run=True)
    contract = ContractPageFactory.create()

    for courserun in courseruns:
        program.add_requirement(courserun.course)

    program.refresh_from_db()

    created, skipped = contract.add_program_courses(program)

    assert created == 3
    assert skipped == 0

    contract.save()
    contract.refresh_from_db()

    assert contract.programs.count() == 1
    assert contract.get_course_runs().count() == 3

    new_courserun = CourseRunFactory.create(is_source_run=True)
    program.add_requirement(new_courserun.course)
    program.save()
    program.refresh_from_db()

    created, skipped = contract.add_program_courses(program)

    assert created == 1
    assert skipped == 3

    contract.save()
    contract.refresh_from_db()

    assert contract.programs.count() == 1
    assert contract.get_course_runs().count() == 4


def test_user_add_b2b_org(mocked_b2b_org_attach):
    """Ensure adding a user to an organization works as expected."""

    orgs = OrganizationPageFactory.create_batch(2)
    user = UserFactory.create()

    # New-style ones
    contract_auto = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )
    contract_managed = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="managed",
        title="Contract Managed",
        name="Contract Managed",
    )
    contract_code = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="code",
        title="Contract Enrollment Code",
        name="Contract Enrollment Code",
    )
    # Legacy ones - these will migrate to "managed" and "code"
    contract_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="sso",
        title="Contract SSO",
        name="Contract SSO",
    )
    contract_non_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="non-sso",
        title="Contract NonSSO",
        name="Contract NonSSO",
    )

    UserOrganization.process_add_membership(user, orgs[0])

    # We should now be in the SSO, auto, and managed contracts
    # but not the other two.

    user.refresh_from_db()
    assert user.b2b_contracts.count() == 3
    assert user.b2b_organizations.filter(organization=orgs[0]).exists()
    assert (
        user.b2b_contracts.filter(
            pk__in=[
                contract_auto.id,
                contract_sso.id,
                contract_managed.id,
            ]
        ).count()
        == 3
    )
    assert (
        user.b2b_contracts.filter(
            pk__in=[
                contract_code.id,
                contract_non_sso.id,
            ]
        ).count()
        == 0
    )


def test_user_remove_b2b_org(mocked_b2b_org_attach):
    """Ensure removing a user from an org also clears the appropriate contracts."""

    orgs = OrganizationPageFactory.create_batch(2)
    user = UserFactory.create()

    # New-style ones
    contract_auto = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )
    contract_managed = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="managed",
        title="Contract Managed",
        name="Contract Managed",
    )
    contract_code = ContractPageFactory.create(
        organization=orgs[1],
        membership_type="code",
        title="Contract Enrollment Code",
        name="Contract Enrollment Code",
    )
    # Legacy ones - these will migrate to "managed" and "code"
    contract_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="sso",
        title="Contract SSO",
        name="Contract SSO",
    )
    contract_non_sso = ContractPageFactory.create(
        organization=orgs[1],
        membership_type="non-sso",
        title="Contract NonSSO",
        name="Contract NonSSO",
    )

    managed_ids = [
        contract_auto.id,
        contract_managed.id,
        contract_sso.id,
    ]
    unmanaged_ids = [
        contract_code.id,
        contract_non_sso.id,
    ]

    UserOrganization.process_add_membership(user, orgs[0])
    UserOrganization.process_add_membership(user, orgs[1])

    user.b2b_contracts.add(contract_code)
    user.b2b_contracts.add(contract_non_sso)
    user.save()

    user.refresh_from_db()

    assert user.b2b_contracts.count() == 5

    UserOrganization.process_remove_membership(user, orgs[1])

    assert user.b2b_contracts.filter(id__in=managed_ids).count() == 3
    assert user.b2b_contracts.filter(id__in=unmanaged_ids).count() == 0

    UserOrganization.process_remove_membership(user, orgs[0])

    # we should have no contracts now since we're no longer in any orgs

    assert user.b2b_contracts.count() == 0


def test_b2b_contract_removal_keeps_enrollments(mocked_b2b_org_attach):
    """Ensure that removing a user from a B2B contract leaves their enrollments alone."""

    org = OrganizationPageFactory.create()
    user = UserFactory.create()

    contract_auto = ContractPageFactory.create(
        organization=org,
        membership_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )

    courserun = CourseRunFactory.create(b2b_contract=contract_auto)

    UserOrganization.process_add_membership(user, org)

    CourseRunEnrollmentFactory(
        user=user,
        run=courserun,
    )

    user.refresh_from_db()

    assert courserun.enrollments.filter(user=user).count() == 1

    UserOrganization.process_remove_membership(user, org)

    assert courserun.enrollments.filter(user=user).count() == 1


def test_b2b_org_attach_calls_keycloak(mocked_b2b_org_attach):
    """Test that attaching a user to an org calls Keycloak successfully."""

    org = OrganizationPageFactory.create()
    user = UserFactory.create()

    UserOrganization.process_add_membership(user, org)

    mocked_b2b_org_attach.assert_called()
