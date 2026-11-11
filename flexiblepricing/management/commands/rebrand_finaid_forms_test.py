"""Tests for the rebrand_finaid_forms command"""

from io import StringIO

import pytest
from django.core.management import call_command

from cms.factories import FlexiblePricingFormFactory
from cms.models import FlexiblePricingRequestForm
from flexiblepricing.constants import FINAID_FORM_TEXTS
from flexiblepricing.management.commands.rebrand_finaid_forms import (
    Command,
    rebrand,
)

pytestmark = pytest.mark.django_db

OLD_INTRO = (
    '<p>Read <a href="https://mitxonline.zendesk.com/hc/en-us/articles/'
    '4409893720347-How-much-do-the-DEDP-courses-cost-">How much do the DEDP '
    "courses cost?</a></p>"
)
OLD_DENIED = (
    "<p>Your request has been denied.</p><p><i>If you have questions, contact us "
    "using the Help button at the bottom of the page, or e-mail "
    "micromasters-support@mit.edu.</i></p>"
)
OLD_PROCESSING = (
    '<p><a href="https://mitxonline.zendesk.com/hc/en-us/sections/'
    '4409903319323-About-Personalized-Pricing">Frequently Asked Questions</a></p>'
    '<p><a href="https://mitxonline.zendesk.com/hc/en-us/requests/new">Contact</a></p>'
)


def _run(*args):
    out = StringIO()
    call_command("rebrand_finaid_forms", *args, stdout=out)
    return out.getvalue()


def test_rebrand_replaces_known_references():
    """Each known MITx Online reference maps to its MIT Learn counterpart."""
    assert rebrand(OLD_INTRO) == (
        '<p>Read <a href="https://support.learn.mit.edu/hc/en-us/articles/'
        '42228071180443-What-is-the-price-for-a-DEDP-course">How much do the DEDP '
        "courses cost?</a></p>"
    )
    assert rebrand(OLD_DENIED) == (
        "<p>Your request has been denied.</p><p><i>If you have questions, contact us "
        'using the <a href="https://support.learn.mit.edu/">MIT Learn help center</a>, '
        "or e-mail mitlearn-support@mit.edu.</i></p>"
    )
    assert rebrand(OLD_PROCESSING) == (
        '<p><a href="https://support.learn.mit.edu/hc/en-us/sections/'
        '42229148190747-About-Personalized-Pricing">Frequently Asked Questions</a></p>'
        '<p><a href="https://support.learn.mit.edu/hc/en-us/requests/new">Contact</a></p>'
    )
    assert rebrand("Learn on MITx Online") == "Learn on MIT Learn"


def test_new_defaults_need_no_rebranding():
    """The defaults new forms start with are already MIT Learn text."""
    for text in FINAID_FORM_TEXTS.values():
        assert rebrand(text) == text
        assert "mitxonline" not in text.lower()
        assert "micromasters-support" not in text


def test_dry_run_changes_nothing():
    """Without --commit the command reports the diff but saves nothing."""
    page = FlexiblePricingFormFactory.create(intro=OLD_INTRO)

    output = _run()

    page.refresh_from_db()
    assert page.intro == OLD_INTRO
    assert "Would update 1 page(s)." in output
    assert '-<p>Read <a href="https://mitxonline.zendesk.com' in output


def test_commit_publishes_live_pages():
    """With --commit, a live page gets a published revision with the new text."""
    page = FlexiblePricingFormFactory.create(
        intro=OLD_INTRO, application_denied_text=OLD_DENIED
    )
    revisions_before = page.revisions.count()

    output = _run("--commit")

    page.refresh_from_db()
    assert page.intro == rebrand(OLD_INTRO)
    assert page.application_denied_text == rebrand(OLD_DENIED)
    assert page.revisions.count() == revisions_before + 1
    assert page.live_revision == page.latest_revision
    assert "Updated 1 page(s)." in output


def test_unknown_references_are_reported_not_changed():
    """An old help center article with no known counterpart is left for a person."""
    custom = '<p><a href="https://mitxonline.zendesk.com/hc/en-us/articles/123-Other">x</a></p>'
    page = FlexiblePricingFormFactory.create(application_approved_text=custom)

    output = _run("--commit")

    page.refresh_from_db()
    assert page.application_approved_text == custom
    assert "needs manual review: application_approved_text" in output


def test_pages_with_drafts_are_skipped():
    """A page with an unpublished draft is not published over."""
    page = FlexiblePricingFormFactory.create(intro=OLD_INTRO)
    page.application_denied_text = "editor's pending change"
    page.save_revision()
    page.refresh_from_db()
    assert page.has_unpublished_changes

    output = _run("--commit")

    page.refresh_from_db()
    assert page.intro == OLD_INTRO
    assert "skipped: page has an unpublished draft" in output


def test_draft_saved_after_load_is_not_published_over():
    """
    A draft saved after the command loaded the page, but before it publishes,
    is still not buried: the page is re-read under a lock before saving.
    """
    page = FlexiblePricingFormFactory.create(intro=OLD_INTRO)
    stale = FlexiblePricingRequestForm.objects.get(pk=page.pk)

    page.application_denied_text = "editor's pending change"
    page.save_revision()

    changed = Command(stdout=StringIO()).rebrand_page(stale, commit=True)

    page.refresh_from_db()
    assert changed is False
    assert page.intro == OLD_INTRO
    assert page.has_unpublished_changes
    assert (
        page.get_latest_revision_as_object().application_denied_text
        == "editor's pending change"
    )


def test_pages_that_are_not_live_get_a_rebranded_draft():
    """
    A page that isn't live is rebranded as a new draft, not published, and a
    second run sees that draft as already rebranded.
    """
    page = FlexiblePricingFormFactory.create(intro=OLD_INTRO)
    page.unpublish()
    page.refresh_from_db()
    assert page.has_unpublished_changes

    output = _run("--commit")

    page.refresh_from_db()
    assert "Updated 1 page(s)." in output
    assert not page.live
    assert page.get_latest_revision_as_object().intro == rebrand(OLD_INTRO)
    assert "Updated 0 page(s)." in _run("--commit")


def test_draft_of_page_that_is_not_live_keeps_editor_changes():
    """Rebranding a page that isn't live builds on its latest draft."""
    page = FlexiblePricingFormFactory.create(intro=OLD_INTRO)
    page.unpublish()
    page.application_denied_text = "editor's pending change"
    page.save_revision()

    _run("--commit")

    draft = FlexiblePricingRequestForm.objects.get(
        pk=page.pk
    ).get_latest_revision_as_object()
    assert draft.intro == rebrand(OLD_INTRO)
    assert draft.application_denied_text == "editor's pending change"


def test_page_rebranded_after_load_is_not_saved_again():
    """If another run rebranded the page meanwhile, no extra revision is saved."""
    page = FlexiblePricingFormFactory.create(intro=OLD_INTRO)
    stale = FlexiblePricingRequestForm.objects.get(pk=page.pk)
    _run("--commit")
    revisions = page.revisions.count()

    changed = Command(stdout=StringIO()).rebrand_page(stale, commit=True)

    assert changed is False
    assert page.revisions.count() == revisions
