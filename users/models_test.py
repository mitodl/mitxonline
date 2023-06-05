"""Tests for user models"""
# pylint: disable=too-many-arguments, redefined-outer-name
import math
import random
from datetime import datetime

import factory
import pytest
import pytz
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from cms.constants import CMS_EDITORS_GROUP_NAME
from openedx.factories import OpenEdxApiAuthFactory, OpenEdxUserFactory
from users.factories import LegalAddressFactory, UserFactory
from users.models import (
    HIGHEST_EDUCATION_CHOICES,
    OPENEDX_HIGHEST_EDUCATION_MAPPINGS,
    LegalAddress,
    User,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "create_func,exp_staff,exp_superuser,exp_is_active",
    [
        [User.objects.create_user, False, False, False],
        [User.objects.create_superuser, True, True, True],
    ],
)
@pytest.mark.parametrize("password", [None, "pass"])
def test_create_user(
    create_func, exp_staff, exp_superuser, exp_is_active, password
):  # pylint: disable=too-many-arguments
    """Test creating a user"""
    username = "user1"
    email = "uSer@EXAMPLE.com"
    name = "Jane Doe"
    with transaction.atomic():
        user = create_func(username, email=email, name=name, password=password)

    assert user.username == username
    assert user.email == "uSer@example.com"
    assert user.name == name
    assert user.get_full_name() == name
    assert user.is_staff is exp_staff
    assert user.is_superuser is exp_superuser
    assert user.is_active is exp_is_active
    if password is not None:
        assert user.check_password(password)

    assert LegalAddress.objects.filter(user=user).exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"is_staff": False},
        {"is_superuser": False},
        {"is_staff": False, "is_superuser": False},
    ],
)
def test_create_superuser_error(kwargs):
    """Test creating a user"""
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            username=None,
            email="uSer@EXAMPLE.com",
            name="Jane Doe",
            password="abc",
            **kwargs,
        )


@pytest.mark.parametrize(
    "field, value, is_valid",
    [
        ["country", "US", True],
        ["country", "United States", False],
    ],
)
def test_legal_address_validation(field, value, is_valid):
    """Verify legal address validation"""
    address = LegalAddress()

    setattr(address, field, value)

    with pytest.raises(ValidationError) as exc:
        address.clean_fields()

    if is_valid:
        assert field not in exc.value.error_dict
    else:
        assert field in exc.value.error_dict


@pytest.mark.django_db
def test_faulty_user_qset():
    """User.faulty_openedx_users should return a User queryset that contains incorrectly configured active Users"""
    users = UserFactory.create_batch(5)
    # An inactive user should not be returned even if they lack auth and openedx user records
    UserFactory.create(is_active=False)
    good_users = users[0:2]
    expected_faulty_users = users[2:]
    OpenEdxApiAuthFactory.create_batch(
        3, user=factory.Iterator(good_users + [users[3]])
    )
    OpenEdxUserFactory.create_batch(3, user=factory.Iterator(good_users + [users[4]]))

    assert set(User.faulty_openedx_users.values_list("id", flat=True)) == {
        user.id for user in expected_faulty_users
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_staff, is_superuser, has_editor_group, exp_is_editor",
    [
        [True, True, True, True],
        [True, False, False, True],
        [False, True, False, True],
        [False, False, True, True],
        [False, False, False, False],
    ],
)
def test_user_is_editor(is_staff, is_superuser, has_editor_group, exp_is_editor):
    """User.is_editor should return True if a user is staff, superuser, or belongs to the 'editor' group"""
    user = UserFactory.create(is_staff=is_staff, is_superuser=is_superuser)
    if has_editor_group:
        user.groups.add(Group.objects.get(name=CMS_EDITORS_GROUP_NAME))
        user.save()
    assert user.is_editor is exp_is_editor


def test_user_age():
    """Tests to make sure the user age is calculated correctly"""

    user = UserFactory.create()

    assert user.get_age() == math.floor(
        datetime.now(tz=pytz.timezone(settings.TIME_ZONE)).year
        - user.user_profile.year_of_birth
    )


@pytest.mark.parametrize("should_pass", [True, False])
def test_user_coppa(should_pass):
    """Tests a user to make sure they're within the range for COPPA"""
    user = UserFactory.create()

    if should_pass:
        user.user_profile.year_of_birth = datetime.now().year - random.randint(13, 100)
    else:
        user.user_profile.year_of_birth = datetime.now().year - random.randint(0, 12)

    assert user.is_coppa_compliant() == should_pass


def test_legal_address_us_state():
    """
    Tests to make sure the us_state property is working properly.

    This should be:
    - the state code alone if the user's country is US and the state is specified
    - None if the state is not specified or if the country is not US
    """

    user = UserFactory.create()
    legal_address = user.legal_address

    legal_address.country = "US"
    legal_address.state = "US-MA"
    legal_address.save()

    assert legal_address.us_state == "MA"

    legal_address.country = "US"
    legal_address.state = None
    legal_address.save()

    assert legal_address.us_state == None

    legal_address.country = "JP"
    legal_address.save()

    assert legal_address.us_state == None


def test_user_profile_edx_education():
    user = UserFactory.create()

    user.user_profile.highest_education = HIGHEST_EDUCATION_CHOICES[
        random.randrange(1, len(HIGHEST_EDUCATION_CHOICES))
    ][0]
    user.save()

    test_openedx_flag = [
        item[1]
        for item in OPENEDX_HIGHEST_EDUCATION_MAPPINGS
        if item[0] == user.user_profile.highest_education
    ][0]

    assert user.user_profile.highest_education is not None
    assert user.user_profile.level_of_education is not None
    assert user.user_profile.level_of_education == test_openedx_flag


@pytest.mark.parametrize("should_exist", [True, False])
def test_user_profile_edx_properties(should_exist):
    user = UserFactory.create()

    user.legal_address.country = "US"

    if should_exist:
        user.user_profile.gender = "f"
        user.legal_address.state = "US-MA"
    else:
        user.user_profile.gender = "nb"
        user.user_profile.state = "US-AS"

    assert (
        user.user_profile.edx_gender == "f"
        if should_exist
        else user.user_profile.edx_gender == "o"
    )
    assert (
        user.legal_address.edx_us_state == "MA"
        if should_exist
        else user.legal_address.edx_us_state is None
    )
