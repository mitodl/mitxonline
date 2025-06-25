from unittest import mock

import pytest

from b2b.factories import ContractPageFactory
from openedx.models import OpenEdxUser
from users.adapters import LearnUserAdapter
from users.factories import UserFactory
from users.models import LegalAddress, UserProfile


@pytest.mark.django_db
def test_init_sets_related_objects():
    user = UserFactory()
    adapter = LearnUserAdapter(user)

    assert isinstance(adapter.user_profile, UserProfile)
    assert isinstance(adapter.legal_address, LegalAddress)
    assert isinstance(adapter.openedx_user, OpenEdxUser)


@pytest.mark.django_db
def test_display_name_returns_name():
    user = UserFactory(name="John Doe")
    adapter = LearnUserAdapter(user)

    assert adapter.display_name == "John Doe"


@pytest.mark.django_db
def test_from_dict_updates_user_and_related():
    user = UserFactory.create(name="Old Name")
    user.legal_address.first_name = "OldFirst"
    user.legal_address.last_name = "OldLast"
    user.legal_address.save()
    adapter = LearnUserAdapter(user)

    contract_page = ContractPageFactory.create(organization__name="Acme Corp")
    data = {
        "fullName": "New Name",
        "name": {"given_name": "NewFirst", "last_name": "NewLast"},
        "organization": "Acme Corp",
    }

    adapter.from_dict(data)
    adapter._save_related()  # noqa: SLF001
    adapter.legal_address.refresh_from_db()
    assert adapter.obj.name == "New Name"
    assert adapter.legal_address.first_name == "NewFirst"
    assert adapter.legal_address.last_name == "NewLast"
    assert user.b2b_contracts.filter(id=contract_page.id).exists()


@pytest.mark.django_db
def test_from_dict_keeps_existing_names_if_missing():
    user = UserFactory.create(name="Old Name")
    user.legal_address.first_name = "OldFirst"
    user.legal_address.last_name = "OldLast"
    user.legal_address.save()
    adapter = LearnUserAdapter(user)

    data = {"fullName": "Another Name", "name": {}}
    adapter.from_dict(data)

    adapter.legal_address.refresh_from_db()

    assert adapter.legal_address.first_name == "OldFirst"
    assert adapter.legal_address.last_name == "OldLast"


@pytest.mark.django_db
def test_save_related_saves_all():
    user = UserFactory()
    adapter = LearnUserAdapter(user)

    adapter.user_profile = mock.MagicMock()
    adapter.legal_address = mock.MagicMock()
    adapter.openedx_user = mock.MagicMock()

    adapter._save_related()  # noqa: SLF001

    adapter.user_profile.save.assert_called_once()
    adapter.legal_address.save.assert_called_once()
    adapter.openedx_user.save.assert_called_once()
