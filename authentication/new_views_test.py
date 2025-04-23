import pytest
from django.urls import reverse
from rest_framework import status
from users.api import User


from fixtures.common import (
    valid_address_dict,
)
from users.models import UserProfile, MALE


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
    resp = client.post(reverse("profile-details-api"), data, content_type="application/json")

    assert resp.status_code == status.HTTP_200_OK
    # Checks that user's name in database is also updated
    assert User.objects.get(pk=user.pk).name == data["name"]

    data = {
        "name": "John Doe",
        "user_profile": {},
    }
    resp = client.post(reverse("profile-details-api"), data, content_type="application/json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST



@pytest.mark.django_db
def test_post_user_extra_detail(mocker, client, user):
    """Test that user can save profile extra details"""
    client.force_login(user)
    data = {
        "gender": MALE,
        "birth_year": "1990",
        "company": "TechCorp",
        "job_title": "Engineer",
        "industry": "Technology",
        "job_function": "Development",
        "years_experience": "5",
        "company_size": 999,
        "leadership_level": "Mid-level",
        "highest_education": "Bachelor's degree",
    }
    resp = client.post(reverse("profile-extra-api"), data, content_type="application/json")

    assert resp.status_code == status.HTTP_200_OK
    user_profile = UserProfile.objects.get(user=user)
    assert user_profile.company == "TechCorp"
    assert user_profile.job_title == "Engineer"

    data = {
        "gender": "",
        "birth_year": "not-a-year",
        "company": "",
    }
    resp = client.post(reverse("profile-extra-api"), data, content_type="application/json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
