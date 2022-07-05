"""
Test end to end django views.
"""
import pytest

pytestmark = [
    pytest.mark.django_db,
]


@pytest.mark.parametrize("url", ["/cms", "/cms/login"])
def test_cms_signin_redirect_to_site_signin(client, url):
    """
    Test that the cms/login redirects users to site signin page.
    """
    response = client.get(url, follow=True)
    assert response.request["PATH_INFO"] == "/signin/"
