"""
Point the text of existing financial aid form pages at MIT Learn.

The form text is stored on each page, so changing the defaults in
flexiblepricing/constants.py only affects forms created afterwards. Editors may
have customized a page, so this only rewrites the specific MITx Online
references it knows how to replace, and lists anything else it finds for a
person to look at.

Without --commit this changes nothing: it prints, per page, a diff of what it
would change and what it would leave for manual review.

A live page is republished with the new text. A page that isn't live gets the
new text as a draft. A live page with an unpublished draft (which includes a
scheduled publish) is skipped, so the editor's pending work isn't published.
"""

import difflib
import re

from django.core.management.base import BaseCommand

from cms.models import FlexiblePricingRequestForm
from flexiblepricing.constants import (
    MIT_LEARN_HELP_CENTER_URL,
    MIT_LEARN_SUPPORT_EMAIL,
    MIT_LEARN_SUPPORT_REQUEST_URL,
)

TEXT_FIELDS = [
    "title",
    "intro",
    "guest_text",
    "application_processing_text",
    "application_approved_text",
    "application_approved_no_discount_text",
    "application_denied_text",
]

MITXONLINE_HELP_CENTER = r"https://mitxonline\.zendesk\.com/hc/en-us"

# (pattern, replacement), applied in order. Article links map to the matching
# MIT Learn help center article; anything else on the old help center is left
# alone and reported, because there is no way to know where it should go.
REPLACEMENTS = [
    (
        rf"{MITXONLINE_HELP_CENTER}/articles/4409893720347-How-much-do-the-DEDP-courses-cost-?",
        f"{MIT_LEARN_HELP_CENTER_URL}hc/en-us/articles/42228071180443-What-is-the-price-for-a-DEDP-course",
    ),
    (
        rf"{MITXONLINE_HELP_CENTER}/sections/4409903319323-About-Personalized-Pricing",
        f"{MIT_LEARN_HELP_CENTER_URL}hc/en-us/sections/42229148190747-About-Personalized-Pricing",
    ),
    (rf"{MITXONLINE_HELP_CENTER}/requests/new", MIT_LEARN_SUPPORT_REQUEST_URL),
    (rf'\s*{MITXONLINE_HELP_CENTER}/?(?=")', MIT_LEARN_HELP_CENTER_URL),
    (
        r"the Help button at the bottom of the page",
        f'the <a href="{MIT_LEARN_HELP_CENTER_URL}">MIT Learn help center</a>',
    ),
    (r"micromasters-support@mit\.edu", MIT_LEARN_SUPPORT_EMAIL),
    (r"MITx Online", "MIT Learn"),
]

# Anything still matching this after the replacements needs a person to decide.
NEEDS_REVIEW = re.compile(r"mitx\s?online|micromasters-support", re.IGNORECASE)


def rebrand(text):
    """Return text with the known MITx Online references replaced."""
    for pattern, replacement in REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    return text


class Command(BaseCommand):
    """Rebrand existing financial aid form pages for MIT Learn."""

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Save and publish the changes. Without this, only print them.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        commit = options["commit"]
        changed = sum(
            self.rebrand_page(page, commit=commit)
            for page in FlexiblePricingRequestForm.objects.order_by("id")
        )
        verb = "Updated" if commit else "Would update"
        self.stdout.write(self.style.SUCCESS(f"{verb} {changed} page(s)."))
        if not commit and changed:
            self.stdout.write("Run again with --commit to apply.")

    def rebrand_page(self, page, *, commit):
        """Report, and with commit apply, one page's changes. True if it changes."""
        label = f"[{page.id}] {page.title} ({page.url_path}, live={page.live})"
        # The page row itself if nothing is unpublished, else the latest draft:
        # save_revision() doesn't write to the row, so that draft is the only
        # place a page that isn't live keeps its current text.
        content = page.get_latest_revision_as_object()
        current = _text(content)
        updates = _updates(current)
        leftovers = {
            field: sorted(set(hits))
            for field, text in {**current, **updates}.items()
            if (hits := NEEDS_REVIEW.findall(text))
        }

        if not updates and not leftovers:
            self.stdout.write(f"{label}: nothing to change")
            return False

        self.stdout.write(self.style.MIGRATE_HEADING(label))
        for field, new in updates.items():
            diff = difflib.unified_diff(
                _lines(current[field]),
                _lines(new),
                fromfile=f"{field} (current)",
                tofile=f"{field} (new)",
                lineterm="",
            )
            self.stdout.write("\n".join(diff))
        for field, hits in leftovers.items():
            self.stdout.write(
                self.style.WARNING(
                    f"  needs manual review: {field} still mentions {hits}"
                )
            )

        if not updates:
            return False
        if page.live and page.has_unpublished_changes:
            # Publishing would put the editor's unfinished (or scheduled) draft
            # live. A page that isn't live always counts as unpublished; its
            # latest revision gets a new draft instead.
            self.stdout.write(
                self.style.WARNING(
                    "  skipped: page has an unpublished draft, update it in Wagtail"
                )
            )
            return False
        if not commit:
            return True

        for field, text in updates.items():
            setattr(content, field, text)
        revision = content.save_revision(log_action=True)
        if page.live:
            revision.publish()
        return True


def _text(content):
    return {field: getattr(content, field) or "" for field in TEXT_FIELDS}


def _updates(text_by_field):
    return {
        field: new
        for field, text in text_by_field.items()
        if (new := rebrand(text)) != text
    }


def _lines(text):
    # Rich text is stored on one line; split at tags so the diff is readable.
    return re.sub(r"(<(?:p|h\d|li|br\s*/?)[ >])", r"\n\1", text or "").splitlines()
