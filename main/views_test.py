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
