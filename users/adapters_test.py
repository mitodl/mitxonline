import pytest

from users.adapters import UserAdapter
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_user_adapter_blank_fields():
    """Test that an incoming request with no name data doesn't blank out fields"""
    user = UserFactory.create(
        name="Joe Smith",
    )

    adapter = UserAdapter(user)
    adapter.from_dict(
        {
            "active": True,
            "userName": "jsmith",
            "externalId": "1",
        }
    )
    adapter.save()

    user.refresh_from_db()

    assert user.name == "Joe Smith"
