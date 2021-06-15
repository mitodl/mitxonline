"""
Test end to end django views.
"""
import json

import pytest
from django.urls import reverse

pytestmark = [
    pytest.mark.django_db,
]


def test_index_view(client):
    """Verify the index view is as expected"""
    response = client.get(reverse("main-index"))
    assert response.status_code == 200
    assert b"Hi, I'm mitx_online" in response.content


def test_json_settings(mocker, settings, client):
    """Verify that webpack bundle src shows up in production"""
    settings.GA_TRACKING_ID = "fake"
    settings.ENVIRONMENT = "test"
    settings.VERSION = "4.5.6"
    settings.USE_WEBPACK_DEV_SERVER = False

    get_bundle = mocker.patch("mitol.common.templatetags.render_bundle._get_bundle")

    response = client.get(reverse("main-index"))

    bundles = [bundle[0][1] for bundle in get_bundle.call_args_list]
    assert set(bundles) == {
        "root",
        "style",
    }
