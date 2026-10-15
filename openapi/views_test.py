"""Tests for API documentation views"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_swagger_ui_lists_every_version(client, settings):
    """The unversioned Swagger UI offers each version's schema in its dropdown"""
    response = client.get(reverse("swagger_ui"))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'layout: "StandaloneLayout"' in content
    for version in settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]:
        assert f'{{"url": "/api/{version}/schema/", "name": "{version}"}}' in content
