"""Test openedx views"""

import pytest
from django.shortcuts import reverse
from rest_framework import status

pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize(
    "route",
    [
        "openedx-private-oauth-complete",
        "openedx-private-oauth-complete-no-apisix",
    ],
)
def test_openedx_private_auth_complete_view(client, route):
    """Verify the openedx_private_auth_complete view returns a 200"""
    response = client.get(reverse(route))
    assert response.status_code == status.HTTP_200_OK
