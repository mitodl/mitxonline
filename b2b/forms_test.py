"""Tests for the B2B Wagtail admin forms."""

import pytest
from django.urls import reverse
from wagtail.test.utils.form_data import inline_formset, nested_form_data, rich_text

from b2b.constants import CONTRACT_MEMBERSHIP_MANAGED
from b2b.factories import ContractPageFactory
from b2b.models import ContractPage

pytestmark = [pytest.mark.django_db]


def _edit_form(contract, user, **changes):
    """Bind the Wagtail edit form for a contract as the given user."""

    form_class = ContractPage.get_edit_handler().get_form_class()
    data = nested_form_data(
        {
            "name": contract.name,
            "description": rich_text(""),
            "welcome_message": "",
            "welcome_message_extra": rich_text(""),
            "organization": contract.organization_id,
            "membership_type": CONTRACT_MEMBERSHIP_MANAGED,
            "google_sheet_target_tab": "Sheet1",
            "active": "on",
            "contract_programs": inline_formset([]),
            **changes,
        }
    )
    form = form_class(data, instance=contract, for_user=user)
    assert form.is_valid(), form.errors
    return form


def test_contract_opt_in_defaults_to_not_recorded():
    """A contract existing is not an opt-in."""

    contract = ContractPageFactory.create()

    assert contract.learner_records_opt_in is False
    assert contract.learner_records_opt_in_recorded_on is None
    assert contract.learner_records_opt_in_recorded_by is None


def test_contract_form_stamps_who_recorded_the_opt_in(admin_user):
    """Checking the opt-in records the editor and the time."""

    contract = ContractPageFactory.create()

    _edit_form(contract, admin_user, learner_records_opt_in="on").save()

    contract.refresh_from_db()
    assert contract.learner_records_opt_in is True
    assert contract.learner_records_opt_in_recorded_by == admin_user
    assert contract.learner_records_opt_in_recorded_on is not None


def test_contract_form_stamps_a_withdrawn_opt_in(admin_user, staff_user):
    """Unchecking the opt-in replaces the stamp with the withdrawal's."""

    contract = ContractPageFactory.create()
    _edit_form(contract, staff_user, learner_records_opt_in="on").save()
    contract.refresh_from_db()
    recorded_on = contract.learner_records_opt_in_recorded_on

    _edit_form(contract, admin_user).save()

    contract.refresh_from_db()
    assert contract.learner_records_opt_in is False
    assert contract.learner_records_opt_in_recorded_by == admin_user
    assert contract.learner_records_opt_in_recorded_on > recorded_on


def test_contract_form_keeps_the_stamp_on_unrelated_edits(admin_user, staff_user):
    """Editing another field doesn't change who recorded the opt-in."""

    contract = ContractPageFactory.create()
    _edit_form(contract, staff_user, learner_records_opt_in="on").save()
    contract.refresh_from_db()
    recorded_on = contract.learner_records_opt_in_recorded_on

    _edit_form(
        contract, admin_user, learner_records_opt_in="on", welcome_message="Hello"
    ).save()

    contract.refresh_from_db()
    assert contract.welcome_message == "Hello"
    assert contract.learner_records_opt_in_recorded_by == staff_user
    assert contract.learner_records_opt_in_recorded_on == recorded_on


def test_contract_opt_in_stamp_survives_a_revision(admin_user):
    """
    A live contract is saved through a revision, so the stamp has to
    round-trip through the revision's content to reach the published page.
    """

    contract = ContractPageFactory.create()
    page = _edit_form(contract, admin_user, learner_records_opt_in="on").save(
        commit=False
    )

    page.save_revision(user=admin_user).publish()

    contract.refresh_from_db()
    assert contract.learner_records_opt_in is True
    assert contract.learner_records_opt_in_recorded_by == admin_user
    assert contract.learner_records_opt_in_recorded_on is not None


def test_contract_revert_does_not_restore_the_old_stamp(admin_user, staff_user):
    """
    Reverting binds the form to the old revision. Going back to a revision
    that was opted in is a new opt-in by whoever reverted, not the original.
    """

    contract = ContractPageFactory.create()
    opted_in = _edit_form(contract, staff_user, learner_records_opt_in="on").save(
        commit=False
    )
    revision = opted_in.save_revision(user=staff_user)
    revision.publish()
    contract.refresh_from_db()
    _edit_form(contract, staff_user).save()

    _edit_form(revision.as_object(), admin_user, learner_records_opt_in="on").save()

    contract.refresh_from_db()
    assert contract.learner_records_opt_in is True
    assert contract.learner_records_opt_in_recorded_by == admin_user


def test_contract_draft_toggle_keeps_the_stamp(admin_user, staff_user):
    """
    Unticking and re-ticking in drafts never changes the stored opt-in, so
    publishing the result leaves the original stamp in place.
    """

    contract = ContractPageFactory.create()
    _edit_form(contract, staff_user, learner_records_opt_in="on").save()
    contract.refresh_from_db()
    recorded_on = contract.learner_records_opt_in_recorded_on

    draft = _edit_form(contract, admin_user).save(commit=False)
    draft = _edit_form(draft, admin_user, learner_records_opt_in="on").save(
        commit=False
    )
    draft.save_revision(user=admin_user).publish()

    contract.refresh_from_db()
    assert contract.learner_records_opt_in is True
    assert contract.learner_records_opt_in_recorded_by == staff_user
    assert contract.learner_records_opt_in_recorded_on == recorded_on


def test_contract_draft_withdrawal_keeps_its_stamp(admin_user, staff_user, user):
    """
    A withdrawal saved as a draft differs from the live contract until it is
    published. Someone else editing another field of that draft must not
    take over the stamp, because its date starts the credential removal.
    """

    contract = ContractPageFactory.create()
    _edit_form(contract, staff_user, learner_records_opt_in="on").save()
    contract.refresh_from_db()

    withdrawn = _edit_form(contract, admin_user).save(commit=False)
    withdrawn.save_revision(user=admin_user)
    contract.refresh_from_db()
    # Read back from the revision, which stores the time to the millisecond.
    draft = contract.get_latest_revision_as_object()
    withdrawn_on = draft.learner_records_opt_in_recorded_on

    edited = _edit_form(draft, user, welcome_message="Hello").save(commit=False)
    edited.save_revision(user=user).publish()

    contract.refresh_from_db()
    assert contract.welcome_message == "Hello"
    assert contract.learner_records_opt_in is False
    assert contract.learner_records_opt_in_recorded_by == admin_user
    assert contract.learner_records_opt_in_recorded_on == withdrawn_on


def test_contract_alias_is_not_opted_in(admin_user, staff_user):
    """
    Wagtail copies every field to an alias, and again whenever the original
    is published. An alias never carries the opt-in.
    """

    contract = ContractPageFactory.create()
    alias = contract.create_alias(update_slug=f"{contract.slug}-alias")

    opted_in = _edit_form(contract, staff_user, learner_records_opt_in="on").save(
        commit=False
    )
    opted_in.save_revision(user=admin_user).publish()

    contract.refresh_from_db()
    alias.refresh_from_db()
    assert contract.learner_records_opt_in is True
    assert alias.learner_records_opt_in is False
    assert alias.learner_records_opt_in_recorded_on is None
    assert alias.learner_records_opt_in_recorded_by is None

    late_alias = contract.create_alias(update_slug=f"{contract.slug}-alias-2")
    late_alias.refresh_from_db()
    assert late_alias.learner_records_opt_in is False
    assert late_alias.learner_records_opt_in_recorded_by is None


def test_contract_copy_is_not_opted_in(staff_user):
    """A copy is a new contract, so it doesn't inherit the opt-in."""

    contract = ContractPageFactory.create()
    _edit_form(contract, staff_user, learner_records_opt_in="on").save()
    contract.refresh_from_db()

    copy = contract.copy(update_attrs={"slug": f"{contract.slug}-copy"})

    copy.refresh_from_db()
    assert copy.learner_records_opt_in is False
    assert copy.learner_records_opt_in_recorded_on is None
    assert copy.learner_records_opt_in_recorded_by is None


def test_contract_edit_page_shows_who_recorded_the_opt_in(admin_client, staff_user):
    """The stamp is shown read-only beside the opt-in in the Wagtail editor."""

    contract = ContractPageFactory.create()
    _edit_form(contract, staff_user, learner_records_opt_in="on").save()

    response = admin_client.get(reverse("wagtailadmin_pages:edit", args=[contract.id]))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="learner_records_opt_in"' in content
    assert 'name="learner_records_opt_in_recorded_by"' not in content
    assert 'name="learner_records_opt_in_recorded_on"' not in content
    assert str(staff_user) in content
