"""Tests for cms views"""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from cms.credential_metadata import (
    CredentialMetadata,
    CredentialMetadataUnavailableError,
)
from cms.factories import CoursePageFactory, ProgramPageFactory, ResourcePageFactory
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


def _url(page):
    return reverse("cms_credential_metadata", args=[page.id])


@pytest.fixture
def mock_fetch(mocker):
    """Mock the MIT Learn client as seen by the view"""
    return mocker.patch("cms.views.fetch_credential_metadata")


@pytest.mark.parametrize("page_factory", [CoursePageFactory, ProgramPageFactory])
def test_credential_metadata_ok(client, admin_user, mock_fetch, page_factory):
    """Stored draft text is returned for course and program parents"""
    page = page_factory.create()
    mock_fetch.return_value = CredentialMetadata(
        readable_id=page.product.readable_id,
        description="A description",
        criteria="- Did a thing",
        errors={"x": "y"},
    )
    client.force_login(admin_user)

    resp = client.get(_url(page))

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "description": "A description",
        "criteria": "- Did a thing",
        "errors": {"x": "y"},
    }
    mock_fetch.assert_called_once_with(page.product.readable_id)


def test_credential_metadata_empty(client, admin_user, mock_fetch):
    """No stored draft is reported as empty, not an error"""
    mock_fetch.return_value = None
    client.force_login(admin_user)

    resp = client.get(_url(CoursePageFactory.create()))

    assert resp.status_code == 200
    assert resp.json() == {"status": "empty"}


def test_credential_metadata_unavailable(client, admin_user, mock_fetch):
    """An unreachable MIT Learn is a 503"""
    mock_fetch.side_effect = CredentialMetadataUnavailableError("down")
    client.force_login(admin_user)

    resp = client.get(_url(CoursePageFactory.create()))

    assert resp.status_code == 503
    assert resp.json() == {"status": "unavailable"}


def test_credential_metadata_wrong_page_type(client, admin_user, mock_fetch):
    """Only course and program pages have credential metadata"""
    client.force_login(admin_user)

    resp = client.get(_url(ResourcePageFactory.create()))

    assert resp.status_code == 404
    mock_fetch.assert_not_called()


def test_credential_metadata_no_page_permission(client, mock_fetch):
    """A CMS user who can't edit the page is refused"""
    user = UserFactory.create()
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    client.force_login(user)

    resp = client.get(_url(CoursePageFactory.create()))

    assert resp.status_code == 403
    mock_fetch.assert_not_called()


def test_credential_metadata_anonymous(client, mock_fetch):
    """Anonymous users are sent to log in"""
    resp = client.get(_url(CoursePageFactory.create()))

    assert resp.status_code == 302
    mock_fetch.assert_not_called()
