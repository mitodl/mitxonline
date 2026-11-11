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


@pytest.mark.parametrize("user_kind", ["anonymous", "with_global_id", "no_global_id"])
def test_dashboard_redirects_to_learn(settings, user_kind):
    """Every visitor is permanently redirected to the MIT Learn dashboard."""
    client = Client()
    if user_kind != "anonymous":
        global_id = "test-global-id" if user_kind == "with_global_id" else None
        client.force_login(UserFactory.create(global_id=global_id))

    response = client.get("/dashboard/", follow=False)

    assert response.status_code == 301
    assert response.url == settings.MIT_LEARN_DASHBOARD_URL


def test_dashboard_redirect_preserves_query_params(settings):
    """Query parameters are forwarded to the learn dashboard redirect URL."""
    response = Client().get("/dashboard/?a=1&b=2", follow=False)

    assert response.status_code == 301
    assert response.url == f"{settings.MIT_LEARN_DASHBOARD_URL}?a=1&b=2"


@pytest.mark.parametrize(
    ("path", "expect_noindex"),
    [
        ("/records/", True),
        ("/records/programs/some-uuid/", True),
        ("/cart/", False),
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
