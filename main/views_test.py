"""
Test end to end django views.
"""

import pytest
from django.urls import reverse

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
