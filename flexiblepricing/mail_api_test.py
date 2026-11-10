"""Tests for flexible pricing (financial aid) emails"""

import re

import pytest
from wagtail.models import Page, Site

from cms.factories import FlexiblePricingFormFactory
from flexiblepricing.constants import FlexiblePriceStatus
from flexiblepricing.factories import FlexiblePriceFactory
from flexiblepricing.mail_api import (
    generate_flexible_price_email,
    send_financial_assistance_request_denied_email,
)
from flexiblepricing.models import FlexiblePrice, FlexiblePricingRequestSubmission

pytestmark = [pytest.mark.django_db]

LEARN_DASHBOARD_URL = "https://learn.example.com/dashboard"
SITE_BASE_URL = "https://mitxonline.example.com"


@pytest.fixture(autouse=True)
def _url_settings(settings):
    settings.MIT_LEARN_DASHBOARD_URL = LEARN_DASHBOARD_URL
    settings.SITE_BASE_URL = SITE_BASE_URL


@pytest.fixture
def mock_send_message(mocker, mocked_responses):
    """Capture sent emails; premailer fetches the base template's web font while inlining CSS"""
    mocked_responses.get("https://fonts.googleapis.com/css")
    return mocker.patch("mitol.mail.api.send_message")


@pytest.fixture
def form_page():
    """A financial aid form under a course page, served from the default Site so it has a URL"""
    form_page = FlexiblePricingFormFactory.create()
    Site.objects.filter(is_default_site=True).update(
        root_page=form_page.get_ancestors().first()
    )
    return form_page


def _flexible_price(status, form_page):
    """A FlexiblePrice for the form's course, submitted through that form"""
    flexible_price = FlexiblePriceFactory.create(
        status=status, courseware_object=form_page.get_parent_courseware()
    )
    flexible_price.cms_submission = FlexiblePricingRequestSubmission.objects.create(
        page=form_page, user=flexible_price.user, form_data="{}"
    )
    flexible_price.save()
    # Reload so cms_submission.page is a plain Page, as it is in production
    return FlexiblePrice.objects.get(pk=flexible_price.pk)


def _sent_email(mock_send_message):
    mock_send_message.assert_called_once()
    message = mock_send_message.call_args[0][0]
    return message.subject, message.body, message.alternatives[0][0]


def _assert_learn_branded(flexible_price, subject, body, html):
    """Greeting by name, MIT Learn sign-off without quotes, no MITx Online mentions"""
    for text in (subject, body, html):
        assert "mitxonline" not in text.lower().replace(SITE_BASE_URL, "")
        assert "mitx online" not in text.lower()
    assert f"Dear {flexible_price.user.name}," in body
    program_name = flexible_price.courseware_object.title
    assert program_name in subject
    assert f"The {program_name} MIT Learn team" in body
    assert '"' not in body.split("Thank you,")[1]


@pytest.mark.parametrize(
    "status",
    [
        FlexiblePriceStatus.APPROVED,
        FlexiblePriceStatus.PENDING_MANUAL_APPROVAL,
        FlexiblePriceStatus.RESET,
    ],
)
def test_flexible_price_email_branding(mock_send_message, form_page, status):
    """Every status email greets the learner and is MIT Learn branded"""
    flexible_price = _flexible_price(status, form_page)
    generate_flexible_price_email(flexible_price)

    _assert_learn_branded(flexible_price, *_sent_email(mock_send_message))


def test_approval_email_links_to_learn_dashboard(mock_send_message, form_page):
    """The approval email sends learners to the MIT Learn dashboard"""
    flexible_price = _flexible_price(FlexiblePriceStatus.APPROVED, form_page)
    generate_flexible_price_email(flexible_price)

    _, body, html = _sent_email(mock_send_message)
    price = flexible_price.tier.discount.friendly_format()
    assert f"financial assistance in the amount of {price}." in body
    assert LEARN_DASHBOARD_URL in body
    # The award and the dashboard link are separate paragraphs
    assert re.search(r"<p>[^<]*amount of[^<]*</p>\s*<p>You can enroll", html)
    assert f'href="{LEARN_DASHBOARD_URL}"' in html


def test_reset_email_links_to_form(mock_send_message, form_page):
    """The reset email links straight to the financial aid form the learner submitted"""
    flexible_price = _flexible_price(FlexiblePriceStatus.RESET, form_page)
    generate_flexible_price_email(flexible_price)

    _, body, html = _sent_email(mock_send_message)
    readable_id = form_page.get_parent_courseware().readable_id
    # The course page URL uses the course's readable_id, not the page slug
    assert form_page.get_parent().slug != readable_id
    form_url = f"{SITE_BASE_URL}/courses/{readable_id}/{form_page.slug}/"
    assert f"using the financial aid form: {form_url}" in body
    assert f'href="{form_url}"' in html


def _assert_reset_links_to_dashboard(mock_send_message, flexible_price):
    generate_flexible_price_email(flexible_price)

    _, body, html = _sent_email(mock_send_message)
    assert f"from your MIT Learn dashboard: {LEARN_DASHBOARD_URL}" in body
    assert "financial aid form" not in body
    assert f'href="{LEARN_DASHBOARD_URL}"' in html


def test_reset_email_without_submission_links_to_dashboard(
    mock_send_message, form_page
):
    """Without a form submission to point at, the reset email links to the Learn dashboard"""
    flexible_price = _flexible_price(FlexiblePriceStatus.RESET, form_page)
    flexible_price.cms_submission = None
    flexible_price.save()
    _assert_reset_links_to_dashboard(mock_send_message, flexible_price)


def test_reset_email_unpublished_form_links_to_dashboard(mock_send_message, form_page):
    """An unpublished form would 404, so the reset email links to the Learn dashboard"""
    flexible_price = _flexible_price(FlexiblePriceStatus.RESET, form_page)
    form_page.unpublish()
    _assert_reset_links_to_dashboard(mock_send_message, flexible_price)


def test_reset_email_unroutable_form_links_to_dashboard(mock_send_message):
    """A form outside every Site has no URL, so the reset email links to the Learn dashboard"""
    form_page = FlexiblePricingFormFactory.create()
    other_root = Page.get_first_root_node().add_child(
        instance=Page(title="Other site", slug="other-site")
    )
    Site.objects.filter(is_default_site=True).update(root_page=other_root)
    Site.clear_site_root_paths_cache()
    assert form_page.get_url_parts() is None
    flexible_price = _flexible_price(FlexiblePriceStatus.RESET, form_page)
    _assert_reset_links_to_dashboard(mock_send_message, flexible_price)


def test_denied_email_greets_learner(mock_send_message, form_page):
    """The staff-written denial email also greets the learner by name"""
    flexible_price = _flexible_price(FlexiblePriceStatus.DENIED, form_page)
    send_financial_assistance_request_denied_email(
        flexible_price, "Your request", "We are unable to approve your request."
    )

    _, body, _ = _sent_email(mock_send_message)
    assert f"Dear {flexible_price.user.name}," in body
    assert "We are unable to approve your request." in body


def test_email_greeting_without_name(mock_send_message, form_page):
    """A learner with no name on file is greeted generically, not with "Dear ,\""""
    flexible_price = _flexible_price(FlexiblePriceStatus.APPROVED, form_page)
    flexible_price.user.name = ""
    flexible_price.user.save()
    generate_flexible_price_email(flexible_price)

    _, body, _ = _sent_email(mock_send_message)
    assert "Dear learner," in body
    assert "Dear ," not in body
