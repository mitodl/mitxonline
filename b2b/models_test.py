"""Tests for models."""

from datetime import timedelta
from importlib import import_module
from uuid import uuid4

import faker
import pytest
from mitol.common.utils import now_in_utc
from wagtail.models import Page

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import (
    CONTRACT_MEMBERSHIP_CODE,
    CONTRACT_MEMBERSHIP_MANAGED,
    PROVISIONING_ACTION_ORG_UPDATED,
)
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import (
    ContractPage,
    ContractProgramItem,
    DiscountContractAttachmentRedemption,
    OrganizationProvisioningAudit,
)
from courses.factories import (
    CourseRunFactory,
    ProgramFactory,
)
from ecommerce.factories import ProductFactory
from users.factories import UserFactory

pytestmark = [pytest.mark.django_db]
FAKE = faker.Faker()


def test_add_program_courses_to_contract(mocker):
    """Test that adding a program to a contract works as expected."""

    mocker.patch("openedx.tasks.clone_courserun.delay")

    program = ProgramFactory.create()
    courseruns = CourseRunFactory.create_batch(
        3, is_source_run=True, language="en", is_primary_language=True
    )
    contract = ContractPageFactory.create()

    for courserun in courseruns:
        program.add_requirement(courserun.course)

    program.refresh_from_db()

    created, no_source = contract.add_program_courses(program)

    assert created == 3
    assert no_source == 0

    contract.save()
    contract.refresh_from_db()

    assert contract.programs.count() == 1
    assert contract.get_course_runs().count() == 3

    new_courserun = CourseRunFactory.create(
        is_source_run=True, language="en", is_primary_language=True
    )
    program.add_requirement(new_courserun.course)
    program.save()
    program.refresh_from_db()

    created, no_source = contract.add_program_courses(program)

    assert created == 1
    assert no_source == 0

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


def test_organization_page_save_without_sso_change_is_not_audited():
    """Creating an organization, or saving one unchanged, writes no audit row."""
    org = OrganizationPageFactory.create(sso_organization_id=uuid4())
    org.name = "Renamed"
    org.save()

    assert not OrganizationProvisioningAudit.objects.filter(organization=org).exists()


def test_organization_page_sso_change_is_audited():
    """A changed sso_organization_id is recorded with the user passed to save."""
    old_id = uuid4()
    new_id = uuid4()
    org = OrganizationPageFactory.create(sso_organization_id=old_id)
    user = UserFactory.create(is_staff=True)

    org.sso_organization_id = new_id
    org.save(user=user)

    audit = OrganizationProvisioningAudit.objects.get(organization=org)
    assert audit.action == PROVISIONING_ACTION_ORG_UPDATED
    assert audit.acting_user == user
    assert audit.org_key == org.org_key
    assert audit.data_before == {"sso_organization_id": str(old_id)}
    assert audit.data_after == {"sso_organization_id": str(new_id)}


def test_organization_page_publish_keeps_provisioned_fields():
    """
    A revision saved before an API write holds the old values. Publishing it
    (a logo upload in the editor, a bulk publish) must not put them back.
    """
    org = OrganizationPageFactory.create(
        name="Old name", description="Old description", sso_organization_id=None
    )
    stale = org.save_revision(user=UserFactory.create(is_staff=True))

    new_id = uuid4()
    org.name = "New name"
    org.description = "New description"
    org.sso_organization_id = new_id
    org.save(audit_sso_link=False)

    stale.publish()

    org.refresh_from_db()
    assert org.name == "New name"
    assert org.title == "New name"
    assert org.description == "New description"
    assert org.sso_organization_id == new_id
    assert not OrganizationProvisioningAudit.objects.filter(organization=org).exists()


def test_organization_page_editor_loads_provisioned_fields_from_the_row():
    """The Wagtail editor shows the stored values, not the latest revision's."""
    org = OrganizationPageFactory.create(name="Old name", sso_organization_id=None)
    org.save_revision()

    new_id = uuid4()
    org.name = "New name"
    org.sso_organization_id = new_id
    org.save(audit_sso_link=False)

    in_editor = org.get_latest_revision_as_object()
    assert in_editor.name == "New name"
    assert in_editor.sso_organization_id == new_id


def test_organization_page_revision_cannot_change_the_sso_link():
    """A revision carrying a different link does not change the stored one."""
    old_id = uuid4()
    org = OrganizationPageFactory.create(sso_organization_id=old_id)

    org.sso_organization_id = uuid4()
    org.save_revision(user=UserFactory.create(is_staff=True)).publish()

    org.refresh_from_db()
    assert org.sso_organization_id == old_id
    assert not OrganizationProvisioningAudit.objects.filter(organization=org).exists()


def test_organization_page_draft_sso_change_is_not_audited():
    """A draft of a live page writes a revision, not the stored link."""
    org = OrganizationPageFactory.create(sso_organization_id=None)

    org.sso_organization_id = uuid4()
    org.save_revision(user=UserFactory.create(is_staff=True))

    assert not OrganizationProvisioningAudit.objects.filter(organization=org).exists()


@pytest.mark.parametrize(
    "as_text",
    [str, lambda sso_id: str(sso_id).upper(), lambda sso_id: sso_id.hex],
    ids=["canonical", "uppercase", "unhyphenated"],
)
def test_organization_page_same_sso_id_as_text_is_not_audited(as_text):
    """The same ID assigned as a str, saved without cleaning, is not a change."""
    sso_id = uuid4()
    org = OrganizationPageFactory.create(sso_organization_id=sso_id)

    org.sso_organization_id = as_text(sso_id)
    org.save(clean=False)

    assert not OrganizationProvisioningAudit.objects.filter(organization=org).exists()


def test_organization_page_sso_change_as_text_is_recorded_in_canonical_form():
    """A new ID assigned as an unhyphenated str is recorded the way it is stored."""
    new_id = uuid4()
    org = OrganizationPageFactory.create(sso_organization_id=None)

    org.sso_organization_id = new_id.hex.upper()
    org.save(clean=False)

    audit = OrganizationProvisioningAudit.objects.get(organization=org)
    assert audit.data_after == {"sso_organization_id": str(new_id)}


def test_organization_page_wagtail_form_edits_only_the_logo():
    """The provisioned fields are read-only panels, so the form has no such fields."""
    org = OrganizationPageFactory.create()
    editor = UserFactory.create(is_staff=True, is_superuser=True)

    form_class = org.get_edit_handler().get_form_class()
    form = form_class(instance=org, for_user=editor)

    assert "logo" in form.fields
    assert not set(org.PROVISIONED_FIELDS) & set(form.fields)


def test_organization_page_sso_audit_can_be_skipped():
    """A caller that writes its own audit record can turn this one off."""
    org = OrganizationPageFactory.create(sso_organization_id=None)

    org.sso_organization_id = uuid4()
    org.save(audit_sso_link=False)

    assert not OrganizationProvisioningAudit.objects.filter(organization=org).exists()


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
    )
    contract2 = ContractPageFactory.create(
        organization=organization,
        membership_type="managed",
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
    )
    managed_contract = ContractPageFactory.create(
        organization=organization,
        membership_type="managed",
    )
    # Non-managed contract (should NOT be removed)
    code_contract = ContractPageFactory.create(
        organization=organization,
        membership_type="code",
    )

    # Create a user and add all contracts
    user = UserFactory.create()
    user.b2b_contracts.add(auto_contract, managed_contract, code_contract)

    # Verify user has all 4 contracts
    assert user.b2b_contracts.count() == 3

    # Remove managed contracts from user
    organization.remove_user_contracts(user)

    # Verify only managed contracts are removed, code contract remains
    user.refresh_from_db()
    assert user.b2b_contracts.count() == 1
    assert not user.b2b_contracts.filter(id=auto_contract.id).exists()
    assert not user.b2b_contracts.filter(id=managed_contract.id).exists()
    assert user.b2b_contracts.filter(id=code_contract.id).exists()


def test_get_unused_discounts(user):
    """Test that get_unused_discounts doesn't include invalid discounts"""

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=10,
    )

    run = CourseRunFactory.create(b2b_only=True)
    run.b2b_contracts.add(contract)
    ProductFactory.create(purchasable_object=run)

    created, _, _ = ensure_enrollment_codes_exist(contract)

    assert created == 10

    code_to_use = contract.get_discounts().last()

    DiscountContractAttachmentRedemption.objects.create(
        discount=code_to_use, user=user, contract=contract
    )

    assert contract.get_unused_discounts().count() == 9
    assert (
        not contract.get_unused_discounts()
        .filter(discount_code=code_to_use.discount_code)
        .exists()
    )


@pytest.mark.parametrize(
    "has_keycloak_id",
    [
        True,
        False,
    ],
)
def test_attach_user_no_sso_id(mocker, has_keycloak_id):
    """Test that attach_user bails out if there's no Keycloak ID"""

    patched_add_membership = mocker.patch(
        "b2b.api.add_user_org_membership", return_value=True
    )

    org = OrganizationPageFactory.create(
        sso_organization_id=uuid4() if has_keycloak_id else None
    )
    user = UserFactory.create()

    result = org.attach_user(user)
    assert result == has_keycloak_id
    assert patched_add_membership.called == has_keycloak_id


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("Plain text stays as it is.", "Plain text stays as it is."),
        ("<p>One</p><p>Two &amp; three</p>", "One\nTwo & three"),
        ("<p>Line<br/>break</p>", "Line\nbreak"),
        (
            '<p>See <a linktype="page" id="3">the page</a></p><p></p><p></p><p>End</p>',
            "See the page\n\nEnd",
        ),
        ("<ul><li>a</li><li>b</li></ul>", "a\nb"),
    ],
)
def test_organization_description_html_to_text(value, expected):
    """The description migration keeps the text and one line per block."""

    migration = import_module(
        "b2b.migrations.0033_organizationpage_description_plain_text"
    )

    assert migration.html_to_text(value) == expected


def test_reconcile_all_user_contracts():
    """Test that the contract reconciliation works as expected"""

    org = OrganizationPageFactory.create()
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_MANAGED, organization=org
    )

    users = UserFactory.create_batch(4)
    for user in users:
        user.b2b_contracts.add(contract)
        user.b2b_organizations.add(org)

    org_only_users = UserFactory.create_batch(2)
    for user in org_only_users:
        user.b2b_organizations.add(org)

    contract_only_users = UserFactory.create_batch(2)
    for user in contract_only_users:
        user.b2b_contracts.add(contract)

    reconciliation_result = org.reconcile_all_user_contracts()

    assert str(contract) in reconciliation_result
    assert len(reconciliation_result[str(contract)]["added"]) == 2
    assert len(reconciliation_result[str(contract)]["removed"]) == 2

    expected_users = [user.id for user in [*users, *org_only_users]]

    b2b_contract_user_qs = contract.b2b_contract_users.filter(
        user__id__in=expected_users
    )

    assert b2b_contract_user_qs.count() == 6

    for user in contract_only_users:
        assert not user.user_b2b_contracts.filter(contract_page=contract).exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"active": False},
        {"contract_end": now_in_utc() - timedelta(days=1)},
        {"contract_start": now_in_utc() + timedelta(days=1)},
    ],
)
def test_contract_not_valid_for_use_can_be_saved(changes):
    """
    A contract that is inactive, ended or not yet started can still be saved,
    and stays out of the relations that code reads valid contracts through.
    """

    contract = ContractPageFactory.create()
    user = UserFactory.create()
    user.b2b_contracts.add(contract)
    run = CourseRunFactory.create()
    run.b2b_contracts.add(contract)

    for field, value in changes.items():
        setattr(contract, field, value)
    contract.save()

    contract = ContractPage.objects.get(pk=contract.pk)
    contract.name = "Renamed"
    contract.save()

    assert Page.objects.get(pk=contract.pk).specific.name == "Renamed"
    assert not ContractPage.active_objects.filter(pk=contract.pk).exists()
    assert not user.b2b_contracts.exists()
    assert not run.b2b_contracts.exists()
    assert not contract.organization.contracts.exists()
    [prefetched] = type(run).objects.filter(pk=run.pk).prefetch_related("b2b_contracts")
    assert list(prefetched.b2b_contracts.all()) == []

    contract.active = True
    contract.contract_start = None
    contract.contract_end = None
    contract.save()

    assert user.b2b_contracts.get() == contract
    assert contract.organization.contracts.get() == contract


def test_publishing_a_stale_contract_revision_keeps_api_written_fields():
    """A Wagtail publish does not put back fields the contract API has changed."""

    contract = ContractPageFactory.create(
        name="Before", max_learners=5, welcome_message="Hello"
    )
    contract.welcome_message_extra = "<p>Old extra</p>"
    revision = contract.save_revision()

    # The contract API saves the row without a revision.
    contract.name = "After"
    contract.max_learners = 50
    contract.welcome_message = "Hello again"
    contract.save()

    # Wagtail's editor starts from the latest revision.
    edited = contract.get_latest_revision_as_object()
    assert edited.name == "After"
    assert edited.max_learners == 50

    edited.welcome_message_extra = "<p>New extra</p>"
    edited.save_revision().publish()

    contract.refresh_from_db()
    assert contract.name == "After"
    assert contract.title == "After"
    assert contract.max_learners == 50
    assert contract.welcome_message == "Hello again"
    assert contract.welcome_message_extra == "<p>New extra</p>"

    # Republishing the revision saved before the API write.
    revision.publish()

    contract.refresh_from_db()
    assert contract.name == "After"
    assert contract.max_learners == 50
    assert contract.welcome_message == "Hello again"
    assert contract.welcome_message_extra == "<p>Old extra</p>"


@pytest.mark.zeal_allow("wagtailcore.Page", "get()")
def test_contract_wagtail_editor_only_edits_what_the_api_does_not(admin_client):
    """The Wagtail edit form loads, links to the dashboard, and can't change API fields."""

    contract = ContractPageFactory.create(name="Read only", max_learners=5)

    response = admin_client.get(f"/cms/pages/{contract.id}/edit/")

    assert response.status_code == 200
    content = response.content.decode()
    assert (
        f"/staff-dashboard/b2b_organizations/show/{contract.organization.org_key}"
        f"/contracts/{contract.id}"
    ) in content
    form = response.context["form"]
    assert not set(contract.PROVISIONED_FIELDS) & set(form.fields)
    assert {"welcome_message_extra", "google_sheet_target"} <= set(form.fields)


def test_publishing_a_contract_revision_keeps_program_links_and_takes_its_order(
    mocker,
):
    """A Wagtail publish reorders a contract's programs and can't add or drop one."""

    queued = mocker.patch("b2b.tasks.create_program_contract_runs.delay")
    contract = ContractPageFactory.create()
    first, second, third = ProgramFactory.create_batch(3)
    ContractProgramItem(contract=contract, program=first, sort_order=0).save(
        skip_run_creation=True
    )
    stale = contract.save_revision()

    # Linked by the contract API after the revision was saved.
    ContractProgramItem(contract=contract, program=second, sort_order=1).save(
        skip_run_creation=True
    )

    def linked_programs():
        return list(
            ContractProgramItem.objects.filter(contract=contract)
            .order_by("sort_order")
            .values_list("program_id", flat=True)
        )

    stale.publish()
    assert linked_programs() == [first.id, second.id]

    # Wagtail's editor starts from the latest revision and sees both.
    edited = contract.get_latest_revision_as_object()
    items = {item.program_id: item for item in edited.contract_programs.all()}
    assert set(items) == {first.id, second.id}

    items[first.id].sort_order = 1
    items[second.id].sort_order = 0
    edited.contract_programs = [
        items[second.id],
        items[first.id],
        ContractProgramItem(program=third, sort_order=2),
    ]
    edited.save_revision().publish()

    assert linked_programs() == [second.id, first.id]
    queued.assert_not_called()

    # A revision that leaves a program out doesn't unlink it. It goes after the
    # programs the revision does have.
    edited = contract.get_latest_revision_as_object()
    edited.contract_programs = [
        item for item in edited.contract_programs.all() if item.program_id == first.id
    ]
    edited.save_revision().publish()

    assert linked_programs() == [first.id, second.id]
