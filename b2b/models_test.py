"""Tests for models."""

import faker
import pytest

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from courses.factories import (
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


def test_organization_page_slug_preserved_on_name_change():
    """Test that the slug is not regenerated when only the name changes."""
    org = OrganizationPageFactory.create(name="MIT")
    original_slug = org.slug

    # Change the name
    org.name = "MIT - Universal AI"
    org.save()
    org.refresh_from_db()

    # The slug should not have changed
    assert org.slug == original_slug
    # But the title should reflect the new name
    assert org.title == "MIT - Universal AI"


def test_organization_page_slug_generated_on_create():
    """Test that the slug is generated when creating a new organization."""
    org = OrganizationPageFactory.create(name="Test Organization", slug="")

    # The slug should have been generated
    assert org.slug == "org-test-organization"
    assert org.title == "Test Organization"


def test_organization_page_slug_not_overwritten_if_set():
    """Test that a manually set slug is not overwritten."""
    org = OrganizationPageFactory.create(name="Test Org", slug="custom-slug")

    # The slug should be the custom one
    assert org.slug == "custom-slug"

    # Change the name
    org.name = "Test Org Updated"
    org.save()
    org.refresh_from_db()

    # The slug should still be the custom one
    assert org.slug == "custom-slug"
    assert org.title == "Test Org Updated"


def test_remove_user_contracts_only_affects_specified_user():
    """Test that remove_user_contracts only removes contracts for the specified user."""

    # Create an organization and contracts
    organization = OrganizationPageFactory.create()
    contract1 = ContractPageFactory.create(
        organization=organization,
        membership_type="auto",
        integration_type="auto",
    )
    contract2 = ContractPageFactory.create(
        organization=organization,
        membership_type="managed",
        integration_type="managed",
    )

    # Create two users and add them both to the contracts
    user1 = UserFactory.create()
    user2 = UserFactory.create()

    user1.b2b_contracts.add(contract1, contract2)
    user2.b2b_contracts.add(contract1, contract2)

    # Verify both users have the contracts
    assert user1.b2b_contracts.count() == 2
    assert user2.b2b_contracts.count() == 2

    # Remove contracts from user1
    organization.remove_user_contracts(user1)

    # Verify user1's contracts are removed
    user1.refresh_from_db()
    assert user1.b2b_contracts.count() == 0

    # Verify user2's contracts are NOT affected
    user2.refresh_from_db()
    assert user2.b2b_contracts.count() == 2
    assert user2.b2b_contracts.filter(id=contract1.id).exists()
    assert user2.b2b_contracts.filter(id=contract2.id).exists()


def test_remove_user_contracts_only_removes_managed_contracts():
    """Test that remove_user_contracts only removes automatically managed contracts."""

    # Create an organization with both managed and non-managed contracts
    organization = OrganizationPageFactory.create()

    # Automatically managed contracts (should be removed)
    auto_contract = ContractPageFactory.create(
        organization=organization,
        membership_type="auto",
        integration_type="auto",
    )
    managed_contract = ContractPageFactory.create(
        organization=organization,
        membership_type="managed",
        integration_type="managed",
    )
    sso_contract = ContractPageFactory.create(
        organization=organization,
        membership_type="sso",
        integration_type="sso",
    )

    # Non-managed contract (should NOT be removed)
    code_contract = ContractPageFactory.create(
        organization=organization,
        membership_type="code",
        integration_type="code",
    )

    # Create a user and add all contracts
    user = UserFactory.create()
    user.b2b_contracts.add(auto_contract, managed_contract, sso_contract, code_contract)

    # Verify user has all 4 contracts
    assert user.b2b_contracts.count() == 4

    # Remove managed contracts from user
    organization.remove_user_contracts(user)

    # Verify only managed contracts are removed, code contract remains
    user.refresh_from_db()
    assert user.b2b_contracts.count() == 1
    assert not user.b2b_contracts.filter(id=auto_contract.id).exists()
    assert not user.b2b_contracts.filter(id=managed_contract.id).exists()
    assert not user.b2b_contracts.filter(id=sso_contract.id).exists()
    assert user.b2b_contracts.filter(id=code_contract.id).exists()
