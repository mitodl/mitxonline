"""Tests for Wagtail API views."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from cms.factories import CoursePageFactory, ProgramPageFactory

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("fully_configured_wagtail"),
]


@pytest.fixture
def anon_client():
    """Anonymous API client with no authentication."""
    return APIClient()


# --- Permission tests (get_permissions) ---


def test_anonymous_can_access_course_pages(anon_client):
    """Anonymous users can list course pages."""
    CoursePageFactory.create(include_in_learn_catalog=True)
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.coursepage"}
    )
    assert resp.status_code == 200


def test_anonymous_can_access_program_pages(anon_client):
    """Anonymous users can list program pages."""
    ProgramPageFactory.create(include_in_learn_catalog=True)
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.programpage"}
    )
    assert resp.status_code == 200


def test_anonymous_can_access_certificate_pages(anon_client):
    """Anonymous users can list certificate pages."""
    CoursePageFactory.create()
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.certificatepage"}
    )
    assert resp.status_code == 200


def test_anonymous_denied_without_type(anon_client):
    """Anonymous users are denied when no type filter is provided."""
    resp = anon_client.get(reverse("wagtailapi:pages:listing"))
    assert resp.status_code == 403


def test_anonymous_denied_for_non_public_page_types(anon_client):
    """Anonymous users are denied for page types that are not publicly accessible."""
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.resourcepage"}
    )
    assert resp.status_code == 403


def test_authenticated_can_list_pages_without_type(user_drf_client):
    """Authenticated users can list pages without specifying a type."""
    resp = user_drf_client.get(reverse("wagtailapi:pages:listing"))
    assert resp.status_code == 200


# --- Queryset filtering tests (get_queryset) ---


def test_anonymous_course_pages_filtered_by_include_in_learn_catalog(anon_client):
    """Anonymous users only see course pages with include_in_learn_catalog=True."""
    visible = CoursePageFactory.create(include_in_learn_catalog=True)
    hidden = CoursePageFactory.create(include_in_learn_catalog=False)
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.coursepage"}
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert visible.id in page_ids
    assert hidden.id not in page_ids


def test_anonymous_program_pages_filtered_by_b2b_only(anon_client):
    """Anonymous users do not see program pages linked to b2b_only programs."""
    visible = ProgramPageFactory.create(include_in_learn_catalog=True)
    b2b_page = ProgramPageFactory.create(
        include_in_learn_catalog=True, program__b2b_only=True
    )
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.programpage"}
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert visible.id in page_ids
    assert b2b_page.id not in page_ids


def test_anonymous_program_pages_filtered_by_include_in_learn_catalog(anon_client):
    """Anonymous users only see program pages with include_in_learn_catalog=True."""
    visible = ProgramPageFactory.create(include_in_learn_catalog=True)
    excluded = ProgramPageFactory.create(include_in_learn_catalog=False)
    resp = anon_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.programpage"}
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert visible.id in page_ids
    assert excluded.id not in page_ids


@pytest.mark.skip_nplusone_check
def test_authenticated_sees_all_course_pages_regardless_of_catalog_flag(
    user_drf_client,
):
    """Authenticated users see all course pages, including those not in the learn catalog."""
    in_catalog = CoursePageFactory.create(include_in_learn_catalog=True)
    not_in_catalog = CoursePageFactory.create(include_in_learn_catalog=False)
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.coursepage"}
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert in_catalog.id in page_ids
    assert not_in_catalog.id in page_ids


def test_authenticated_sees_b2b_program_pages(user_drf_client):
    """Authenticated users see program pages for b2b_only programs."""
    b2b_page = ProgramPageFactory.create(program__b2b_only=True)
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.programpage"}
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert b2b_page.id in page_ids


# --- ReadableIDFilter tests ---


def test_readable_id_filter_returns_matching_course_page(user_drf_client):
    """Filtering by readable_id returns only the page with the matching course readable_id."""
    target = CoursePageFactory.create()
    other = CoursePageFactory.create()
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:listing"),
        {"type": "cms.coursepage", "readable_id": target.course.readable_id},
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert target.id in page_ids
    assert other.id not in page_ids


def test_readable_id_filter_replaces_spaces_with_plus(user_drf_client):
    """Spaces in the readable_id query param are treated as + signs (URL encoding)."""
    target = CoursePageFactory.create()
    # Course readable_ids follow the format "course-v1:PyT+Course{n}", so replacing
    # + with a space simulates a URL-decoded parameter that the filter should normalize.
    readable_id_with_space = target.course.readable_id.replace("+", " ")
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:listing"),
        {"type": "cms.coursepage", "readable_id": readable_id_with_space},
    )
    assert resp.status_code == 200
    page_ids = [item["id"] for item in resp.json()["items"]]
    assert target.id in page_ids


# --- detail_view tests ---


def test_detail_view_returns_correct_page(user_drf_client):
    """The detail endpoint returns the correct page by primary key."""
    page = CoursePageFactory.create()
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:detail", kwargs={"pk": page.id})
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == page.id


def test_detail_view_certificate_page_with_valid_revision(user_drf_client):
    """Requesting a certificate page with a valid revision_id returns that revision."""
    course_page = CoursePageFactory.create()
    cert_page = course_page.certificate_page
    revision = cert_page.save_revision()
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:detail", kwargs={"pk": cert_page.id}),
        {"revision_id": revision.id},
    )
    assert resp.status_code == 200


def test_detail_view_certificate_page_with_invalid_revision_returns_404(
    user_drf_client,
):
    """Requesting a certificate page with a nonexistent revision_id returns 404."""
    course_page = CoursePageFactory.create()
    cert_page = course_page.certificate_page
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:detail", kwargs={"pk": cert_page.id}),
        {"revision_id": 999999},
    )
    assert resp.status_code == 404


def test_detail_view_non_certificate_page_ignores_revision_id(user_drf_client):
    """Passing revision_id when requesting a non-certificate page has no effect."""
    page = CoursePageFactory.create()
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:detail", kwargs={"pk": page.id}),
        {"revision_id": 999999},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == page.id


# --- Meta field tests ---


def test_listing_response_includes_live_in_meta(user_drf_client):
    """Course page listing responses include 'live' in each item's meta."""
    CoursePageFactory.create()
    resp = user_drf_client.get(
        reverse("wagtailapi:pages:listing"), {"type": "cms.coursepage"}
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    assert "live" in items[0]["meta"]
    assert "last_published_at" in items[0]["meta"]
