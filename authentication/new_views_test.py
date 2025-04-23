import pytest
from django.urls import reverse
from rest_framework import status
from users.api import User


from fixtures.common import (
    valid_address_dict,
)

@pytest.mark.django_db
def test_post_user_profile_detail(mocker, valid_address_dict, client, user):
    """Test that user can save profile details"""
    client.force_login(user)
    data = {
        "name": "John Doe",
        "username": "johndoe",
        "legal_address": valid_address_dict,
        "user_profile": {},
    }
    resp = client.post(reverse("profile-details"), data, content_type="application/json")

    assert resp.status_code == status.HTTP_200_OK
    # assert resp.data["name"] == data["name"]
    # Checks that user's name in database is also updated
    assert User.objects.get(pk=user.pk).name == data["name"]
