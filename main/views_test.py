"""
Test end to end django views.
"""
import pytest
from django.urls import reverse

pytestmark = [
    pytest.mark.django_db,
]


def test_json_settings(mocker, settings, client):
    """Verify that webpack bundle src shows up in production"""
    settings.GA_TRACKING_ID = "fake"
    settings.ENVIRONMENT = "test"
    settings.VERSION = "4.5.6"
    settings.USE_WEBPACK_DEV_SERVER = False

    get_bundle = mocker.patch("mitol.common.templatetags.render_bundle._get_bundle")

    # Use the login page just as an example of a page that should have bundles included
    client.get(reverse("login"))

    bundles = [bundle[0][1] for bundle in get_bundle.call_args_list]
    assert set(bundles) == {
        "django",
        "root",
        "style",
    }


@pytest.mark.parametrize("url", ["/cms", "/cms/login"])
def test_cms_signin_redirect_to_site_signin(client, url):
    """
    Test that the cms/login redirects users to site signin page.
    """
    response = client.get(url, follow=True)
    assert response.request["PATH_INFO"] == "/signin/"
