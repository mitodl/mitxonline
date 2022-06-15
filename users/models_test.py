"""Tests for user models"""
# pylint: disable=too-many-arguments, redefined-outer-name
import factory
import pytest
import unicodedata
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction

from cms.constants import CMS_EDITORS_GROUP_NAME
from openedx.factories import OpenEdxApiAuthFactory, OpenEdxUserFactory
from users.factories import UserFactory
from users.models import LegalAddress, User

pytestmark = pytest.mark.django_db


def normalize_username(username):
    """Strips non-ASCII characters from the username."""
    normalized_username = unicodedata.normalize("NFD", username)
    normalized_username = normalized_username.encode("ascii", "ignore").decode("utf-8")
    return str(normalized_username)


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
    assert user.normalized_username == normalize_username(username)
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


@pytest.mark.django_db
def test_username_normalization():
    """
    Tests the make_normalized_username function for proper functionality. This
    doesn't strictly require a User object, so this uses a set string with
    accented characters that should be normalized to low-ASCII characters.
    (For completeness, this also tests the version of the function here.)
    """

    accented_string = "åéîøüäëïñç"
    unaccented_string = "aeiouaeinc"
