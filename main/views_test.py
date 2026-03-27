"""
Test end to end django views.
"""

import pytest
from django.test import Client
from django.urls import reverse

from users.factories import UserFactory

pytestmark = [
    pytest.mark.django_db,
]


def test_cms_signin_redirect_to_site_signin(client):
    """Test redirect from CMS login to site login."""
    # Test direct call to CMS login redirect
    response = client.get("/cms/login", follow=False)
    assert response.status_code == 302
    expected_redirect = "/login/?next=http%3A//testserver/cms/"
    assert response.url == expected_redirect


@pytest.mark.parametrize("url_name", ["user-dashboard", "staff-dashboard"])
def test_never_cache_react_views(staff_client, url_name):
    """
    Test that our react views instruct any clients not to cache the response
    """
    response = staff_client.get(reverse(url_name))

    assert (
        response.headers["Cache-Control"]
        == "max-age=0, no-cache, no-store, must-revalidate, private"
    )


@pytest.mark.parametrize(
    "flag_enabled",
    [True, False],
)
def test_dashboard_redirect(settings, mocker, flag_enabled):
    """Authenticated users with global_id are redirected when the flag is enabled."""
    user = UserFactory.create(global_id="test-global-id")
    client = Client()
    client.force_login(user)

    mocker.patch("main.views.is_enabled", return_value=flag_enabled)

    response = client.get("/dashboard/", follow=False)

    if flag_enabled:
        assert response.status_code == 302
        assert response.url == settings.MIT_LEARN_DASHBOARD_URL
    else:
        assert response.status_code == 200


def test_dashboard_redirect_preserves_query_params(settings, mocker):
    """Query parameters are forwarded to the learn dashboard redirect URL."""
    user = UserFactory.create(global_id="test-global-id")
    client = Client()
    client.force_login(user)

    mocker.patch("main.views.is_enabled", return_value=True)

    response = client.get("/dashboard/?a=1&b=2", follow=False)

    assert response.status_code == 302
    assert response.url == f"{settings.MIT_LEARN_DASHBOARD_URL}?a=1&b=2"


def test_dashboard_no_redirect_without_global_id(mocker):
    """Authenticated users without a global_id are never redirected."""
    user = UserFactory.create(global_id=None)
    client = Client()
    client.force_login(user)

    mock_is_enabled = mocker.patch("main.views.is_enabled")

    response = client.get("/dashboard/")

    mock_is_enabled.assert_not_called()
    assert response.status_code == 200


def test_dashboard_no_redirect_for_anonymous(client, mocker):
    """Unauthenticated users are never redirected and never check the flag."""
    mock_is_enabled = mocker.patch("main.views.is_enabled")

    response = client.get("/dashboard/")

    mock_is_enabled.assert_not_called()
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("path", "expect_noindex"),
    [
        ("/records/", True),
        ("/records/programs/some-uuid/", True),
        ("/dashboard/", False),
    ],
)
def test_noindex_meta_on_learner_records(client, settings, path, expect_noindex):
    """Learner records pages should include a noindex meta tag, even in production."""
    settings.ENVIRONMENT = "production"  # Other envs always have noindex
    response = client.get(path)
    content = response.content.decode()
    if expect_noindex:
        assert '<meta name="robots" content="noindex">' in content
    else:
        assert '<meta name="robots" content="noindex">' not in content
