"""Test for user views"""

from datetime import timedelta

import pytest
from django.urls import reverse
from factory import fuzzy
from mitol.common.utils import now_in_utc
from rest_framework import status
from social_django.models import UserSocialAuth

from b2b.factories import ContractPageFactory
from main.test_utils import drf_datetime
from users.api import User
from users.factories import UserFactory
from users.models import ChangeEmailRequest


@pytest.mark.django_db
def test_cannot_create_user(client):
    """Verify the api to create a user is nonexistent"""
    resp = client.post("/api/users/", data={"name": "Name"})

    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_update_user(user_client, user):
    """Verify the api to update a user is doesn't accept the verb"""
    resp = user_client.patch(
        reverse("users_api-detail", kwargs={"pk": user.id}), data={"name": "Name"}
    )

    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_get_user_by_id(user_client, user):
    """Test that user can request their own user by id"""
    resp = user_client.get(reverse("users_api-detail", kwargs={"pk": user.id}))

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {
        "id": user.id,
        "username": user.edx_username,
        "name": user.name,
        "created_on": drf_datetime(user.created_on),
        "updated_on": drf_datetime(user.updated_on),
    }


@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize("has_orgs", [True, False])
def test_get_user_by_me(mocker, client, user, is_anonymous, has_orgs):
    """Test that user can request their own user by the 'me' alias"""
    b2b_orgs = []

    if not is_anonymous:
        client.force_login(user)

        if has_orgs:
            contract = ContractPageFactory.create()
            user.b2b_organizations.add(contract.organization)
            user.b2b_contracts.add(contract)
            user.save()
            b2b_orgs = [
                {
                    "id": contract.organization.id,
                    "name": contract.organization.name,
                    "description": contract.organization.description,
                    "logo": None,
                    "slug": contract.organization.slug,
                    "contracts": [
                        {
                            "id": contract.id,
                            "name": contract.name,
                            "description": contract.description,
                            "membership_type": contract.membership_type,
                            "integration_type": contract.integration_type,
                            "contract_start": None,
                            "contract_end": None,
                            "active": True,
                            "slug": contract.slug,
                            "organization": contract.organization.id,
                        }
                    ],
                }
            ]

    resp = client.get(reverse("users_api-me"))

    assert resp.status_code == status.HTTP_200_OK

    if is_anonymous:
        assert resp.json() == {
            "id": None,
            "username": None,
            "email": None,
            "legal_address": None,
            "is_anonymous": True,
            "is_authenticated": False,
            "is_staff": False,
            "is_superuser": False,
            "grants": [],
            "user_profile": None,
            "is_active": False,
            "b2b_organizations": b2b_orgs,
        }
    else:
        assert resp.json() == {
            "id": user.id,
            "username": user.edx_username,
            "email": user.email,
            "name": user.name,
            "legal_address": {
                "country": user.legal_address.country,
                "state": user.legal_address.state,
            },
            "user_profile": {
                "gender": user.user_profile.gender,
                "year_of_birth": user.user_profile.year_of_birth,
                "addl_field_flag": user.user_profile.addl_field_flag,
                "company": user.user_profile.company,
                "job_title": user.user_profile.job_title,
                "industry": user.user_profile.industry,
                "job_function": user.user_profile.job_function,
                "company_size": user.user_profile.company_size,
                "years_experience": user.user_profile.years_experience,
                "leadership_level": user.user_profile.leadership_level,
                "highest_education": user.user_profile.highest_education,
                "type_is_student": user.user_profile.type_is_student,
                "type_is_professional": user.user_profile.type_is_professional,
                "type_is_educator": user.user_profile.type_is_educator,
                "type_is_other": user.user_profile.type_is_other,
            },
            "is_anonymous": False,
            "is_authenticated": True,
            "is_editor": False,
            "created_on": drf_datetime(user.created_on),
            "updated_on": drf_datetime(user.updated_on),
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "grants": list(user.get_all_permissions()),
            "is_active": True,
            "b2b_organizations": b2b_orgs,
        }


@pytest.mark.parametrize(
    ("is_anonymous", "has_openedx_user", "has_edx_username"),
    [
        (True, True, True),
        (True, True, False),
        (True, False, False),
        (False, True, True),
        (False, True, False),
        (False, False, False),
    ],
)
def test_get_userinfo(client, user, is_anonymous, has_openedx_user, has_edx_username):
    """Tests userinfo endpoint when user is anonymous, has no edx_username, or is valid"""
    b2b_orgs = []

    if not is_anonymous:
        client.force_login(user)

    if not has_openedx_user:
        user.openedx_users.all().delete()

    if has_openedx_user and not has_edx_username:
        openedx_user = user.openedx_users.first()
        openedx_user.edx_username = None
        openedx_user.save()

    resp = client.get(reverse("userinfo_api"))

    if is_anonymous or not has_openedx_user or not has_edx_username:
        assert resp.status_code == status.HTTP_409_CONFLICT
    else:
        assert resp.status_code == status.HTTP_200_OK

    if is_anonymous or not has_openedx_user or not has_edx_username:
        assert resp.json() == {"error": "User has no edx_username."}
    else:
        assert resp.json() == {
            "id": user.id,
            "username": user.edx_username,
            "email": user.email,
            "name": user.name,
            "legal_address": {
                "country": user.legal_address.country,
                "state": user.legal_address.state,
            },
            "user_profile": {
                "gender": user.user_profile.gender,
                "year_of_birth": user.user_profile.year_of_birth,
                "addl_field_flag": user.user_profile.addl_field_flag,
                "company": user.user_profile.company,
                "job_title": user.user_profile.job_title,
                "industry": user.user_profile.industry,
                "job_function": user.user_profile.job_function,
                "company_size": user.user_profile.company_size,
                "years_experience": user.user_profile.years_experience,
                "leadership_level": user.user_profile.leadership_level,
                "highest_education": user.user_profile.highest_education,
                "type_is_student": user.user_profile.type_is_student,
                "type_is_professional": user.user_profile.type_is_professional,
                "type_is_educator": user.user_profile.type_is_educator,
                "type_is_other": user.user_profile.type_is_other,
            },
            "is_anonymous": False,
            "is_authenticated": True,
            "is_editor": False,
            "created_on": drf_datetime(user.created_on),
            "updated_on": drf_datetime(user.updated_on),
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "grants": list(user.get_all_permissions()),
            "is_active": True,
            "b2b_organizations": b2b_orgs,
        }


@pytest.mark.django_db
def test_countries_states_view(client):
    """Test that a list of countries and states is returned"""
    resp = client.get(reverse("countries_api-list"))
    countries = {country["code"]: country for country in resp.json()}
    assert len(countries.get("US").get("states")) > 50
    assert {"code": "CA-QC", "name": "Quebec"} in countries.get("CA").get("states")
    assert len(countries.get("FR").get("states")) == 0
    assert countries.get("US").get("name") == "United States"
    assert countries.get("TW").get("name") == "Taiwan"


def test_create_email_change_request_invalid_password(user_drf_client, user):
    """Test that invalid password is returned"""
    resp = user_drf_client.post(
        "/api/change-emails/",
        data={
            "new_email": "abc@example.com",
            "password": user.password,
            "old_password": "abc",
        },
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_create_email_change_request_existing_email(user_drf_client, user):
    """Test that create change email request gives validation error for existing user email"""
    new_user = UserFactory.create()
    user_password = user.password
    user.set_password(user.password)
    user.save()
    resp = user_drf_client.post(
        "/api/change-emails/",
        data={"new_email": new_user.email, "password": user_password},
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_create_email_change_request_same_email(user_drf_client, user):
    """Test that user same email wouldn't be processed"""
    resp = user_drf_client.post(
        "/api/change-emails/",
        data={
            "new_email": user.email,
            "password": user.password,
            "old_password": user.password,
        },
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_create_email_change_request_valid_email(user_drf_client, user, mocker):
    """Test that change request is created"""
    user_password = user.password
    user.set_password(user.password)
    user.save()

    mocker.patch("openedx.tasks.change_edx_user_email_async", return_value=None)
    mocker.patch("openedx.tasks.api.update_edx_user_email")
    mock_email = mocker.patch("mail.verification_api.send_verify_email_change_email")
    resp = user_drf_client.post(
        "/api/change-emails/",
        data={"new_email": "abc@example.com", "password": user_password},
    )

    assert resp.status_code == status.HTTP_201_CREATED

    code = mock_email.call_args[0][1].code
    assert code

    old_email = user.email
    resp = user_drf_client.patch(
        f"/api/change-emails/{code}/", data={"confirmed": True}
    )
    assert not UserSocialAuth.objects.filter(uid=old_email, user=user).exists()
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.email == "abc@example.com"


def test_create_email_change_request_expired_code(user_drf_client, user):
    """Check for expired code for Email Change Request"""
    change_request = ChangeEmailRequest.objects.create(
        user=user,
        new_email="abc@example.com",
        expires_on=now_in_utc() - timedelta(seconds=5),
    )

    resp = user_drf_client.patch(
        f"/api/change-emails/{change_request.code}/", data={"confirmed": True}
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_update_email_change_request_invalid_token(user_drf_client):
    """Test that invalid token doesn't work"""
    resp = user_drf_client.patch("/api/change-emails/abc/", data={"confirmed": True})
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_update_user_name_change(mocker, user_client, user, valid_address_dict):
    """Test that updating user's name is properly reflected in MITx Online"""
    new_name = fuzzy.FuzzyText(prefix="Test-").fuzz()
    mocker.patch("openedx.api.update_edx_user_name")
    mocker.patch("openedx.api.update_edx_user_profile")
    payload = {
        "name": new_name,
        "email": user.email,
        "legal_address": valid_address_dict,
        "user_profile": None,
    }

    resp = user_client.patch(
        reverse("users_api-me"), content_type="application/json", data=payload
    )

    assert resp.status_code == status.HTTP_200_OK
    # Checks that returned response has updated name
    assert resp.data["name"] == new_name
    # Checks that user's name in database is also updated
    assert User.objects.get(pk=user.pk).name == new_name


def test_update_user_name_change_edx(mocker, user_client, user, valid_address_dict):
    """Test that PATCH on user/me also calls update user's name api in edX if there is a name change in MITx Online"""
    new_name = fuzzy.FuzzyText(prefix="Test-").fuzz()
    update_edx_mock = mocker.patch("openedx.api.update_edx_user_name")
    mocker.patch("openedx.api.update_edx_user_profile")
    payload = {
        "name": new_name,
        "email": user.email,
        "legal_address": valid_address_dict,
        "user_profile": None,
    }
    resp = user_client.patch(
        reverse("users_api-me"), content_type="application/json", data=payload
    )

    assert resp.status_code == status.HTTP_200_OK
    # Checks that update edx user was called and only once when there was a change in user's name(Full Name)
    update_edx_mock.assert_called_once_with(user)


def test_update_user_no_name_change_edx(mocker, user_client, user, valid_address_dict):
    """
    Test that PATCH on user/me without name change doesn't call update user's
    name in edX, but that the profile update is called.
    """
    update_edx_mock = mocker.patch("openedx.api.update_edx_user_name")
    update_edx_profile_mock = mocker.patch("openedx.api.update_edx_user_profile")
    resp = user_client.patch(
        reverse("users_api-me"),
        content_type="application/json",
        data={
            "name": user.name,
            "email": user.email,
            "legal_address": valid_address_dict,
            "user_profile": None,
        },
    )

    assert resp.status_code == status.HTTP_200_OK
    # Checks that update edx user was called not called when there is no change in user's name(Full Name)
    update_edx_mock.assert_not_called()
    update_edx_profile_mock.assert_called()
