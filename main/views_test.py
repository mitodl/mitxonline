"""
Test end to end django views.
"""
from django.urls import reverse
import pytest
from main import features
from rest_framework import status

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


@pytest.mark.parametrize("enable_new_design", [True, False])
def test_catalog_page_feature_flag(client, settings, enable_new_design):
    """
    Test that our react views instruct any clients not to cache the response
    """
    settings.FEATURES[features.ENABLE_NEW_DESIGN] = enable_new_design
    response = client.get("/catalog", follow=True)
    if enable_new_design:
        assert response.status_code == status.HTTP_200_OK
    else:
        assert response.status_code == status.HTTP_404_NOT_FOUND
