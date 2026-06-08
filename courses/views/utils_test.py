"""Test for view utilities."""

import pytest

from courses.permissions import IsEtlUser
from users.factories import UserFactory

pytestmark = [
    pytest.mark.django_db,
]


@pytest.mark.parametrize(
    "is_etl",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "is_superuser",
    [
        False,
        True,
    ],
)
def test_is_etl_permission(rf, is_etl, is_superuser):
    """Test that the IsEtlUser permission class works as expected."""

    user = UserFactory.create(is_etl=is_etl, is_superuser=is_superuser)

    request = rf.get("/")
    request.user = user

    perm = IsEtlUser()

    assert perm.has_permission(request, {}) == (is_etl or is_superuser)
