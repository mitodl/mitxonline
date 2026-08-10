import pytest
from mitol.scim.requests import InMemoryHttpRequest

from users.adapters import LearnUserAdapter
from users.factories import UserFactory

pytestmark = pytest.mark.django_db


def _adapter(user):
    """LearnUserAdapter needs a request for to_dict()'s meta/location, same as
    the real sync code (mitol.scim.api._get_sync_operations) provides.
    """
    return LearnUserAdapter(user, InMemoryHttpRequest.stub())


def test_learn_user_adapter_to_dict_uses_legal_address_name():
    """to_dict() should use legal_address first/last name when both are set"""
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "Given"
    user.legal_address.last_name = "Family"
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {
        "givenName": "Given",
        "familyName": "Family",
    }


def test_learn_user_adapter_to_dict_falls_back_to_split_name():
    """to_dict() splits User.name when legal_address has no name on file"""
    user = UserFactory.create(name="Joe Middle Smith")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {
        "givenName": "Joe Middle",
        "familyName": "Smith",
    }


def test_learn_user_adapter_to_dict_single_token_name():
    """A single-token name can't be split; givenName gets it, familyName is blank"""
    user = UserFactory.create(name="Madonna")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {
        "givenName": "Madonna",
        "familyName": "",
    }


def test_learn_user_adapter_to_dict_no_name_data():
    """No legal_address and no User.name results in a blank given/family name"""
    user = UserFactory.create(name="")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {"givenName": "", "familyName": ""}


def test_learn_user_adapter_to_dict_partial_legal_address_falls_back():
    """A half-filled legal_address isn't trusted; falls back to splitting name"""
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "OnlyGiven"
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {
        "givenName": "Joe",
        "familyName": "Smith",
    }


def test_learn_user_adapter_from_dict_writes_legal_address():
    """from_dict() writes incoming name.givenName/familyName onto legal_address"""
    user = UserFactory.create(name="Joe Smith")
    adapter = LearnUserAdapter(user)

    adapter.from_dict(
        {
            "active": True,
            "userName": "jsmith",
            "externalId": "1",
            "name": {"givenName": "New", "familyName": "Name"},
        }
    )
    adapter.save()

    user.refresh_from_db()

    assert user.legal_address.first_name == "New"
    assert user.legal_address.last_name == "Name"


def test_learn_user_adapter_from_dict_explicit_null_name_does_not_blank_out():
    """An explicit JSON null for givenName/familyName is treated the same as an
    absent key - it must not overwrite legal_address with None, since those
    are non-nullable CharFields and would raise an IntegrityError on save
    """
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    adapter = LearnUserAdapter(user)
    adapter.from_dict(
        {
            "active": True,
            "userName": "jsmith",
            "externalId": "1",
            "name": {"givenName": None, "familyName": None},
        }
    )
    adapter.save()

    user.refresh_from_db()

    assert user.legal_address.first_name == "Joe"
    assert user.legal_address.last_name == "Smith"


def test_learn_user_adapter_from_dict_blank_name_does_not_blank_out():
    """An empty or whitespace-only string for givenName/familyName is treated
    the same as absent/null - it must not silently overwrite a previously
    valid legal_address name with blank data
    """
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    adapter = LearnUserAdapter(user)
    adapter.from_dict(
        {
            "active": True,
            "userName": "jsmith",
            "externalId": "1",
            "name": {"givenName": "", "familyName": "   "},
        }
    )
    adapter.save()

    user.refresh_from_db()

    assert user.legal_address.first_name == "Joe"
    assert user.legal_address.last_name == "Smith"


def test_learn_user_adapter_blank_fields():
    """An incoming request with no name data doesn't blank out existing fields"""
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    adapter = LearnUserAdapter(user)
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
    assert user.legal_address.first_name == "Joe"
    assert user.legal_address.last_name == "Smith"
