"""Tests for models."""

import faker
import pytest

from b2b.factories import ContractPageFactory, OrganizationPageFactory
from courses.factories import CourseRunFactory, ProgramFactory

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


def test_add_program_courses_to_contract(mocker):
    """Test that adding a program to a contract works as expected."""

    mocker.patch("openedx.tasks.clone_courserun.delay")

    program = ProgramFactory.create()
    courseruns = CourseRunFactory.create_batch(3)
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

    new_courserun = CourseRunFactory.create()
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
