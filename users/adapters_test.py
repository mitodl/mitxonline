import pytest
from mitol.scim.requests import InMemoryHttpRequest

from users.adapters import (
    EDX_SYNC_ATTRS,
    EDX_UNSYNCED_ATTRS,
    LearnUserAdapter,
)
from users.factories import UserFactory
from users.models import User

pytestmark = pytest.mark.django_db


def _adapter(user):
    """LearnUserAdapter needs a request for to_dict()'s meta/location, same as
    the real sync code (mitol.scim.api._get_sync_operations) provides.
    """
    return LearnUserAdapter(user, InMemoryHttpRequest.stub())


def test_attr_map_has_no_orm_style_double_underscore_paths():
    """ATTR_MAP values are consumed via a plain setattr() by both
    django_scim's (django_scim.adapters.SCIMUser.handle_replace) and mitol's
    (mitol.scim.adapters.UserAdapter._handle_resplace_nested_path) PATCH
    add/replace dispatch - neither walks a "__" double-underscore path into
    a related object. A mapped value containing "__" (e.g. the
    "legal_address__first_name" this PR removed) would silently set a
    bogus flat attribute of that literal name on the user instead of
    updating legal_address.first_name, and never raise - a real SCIM PATCH
    to name.givenName would corrupt nothing visibly while doing nothing
    useful either.
    """
    for target in LearnUserAdapter.ATTR_MAP.values():
        assert "__" not in target


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


def test_learn_user_adapter_to_dict_sends_full_name_separately():
    """to_dict() always sends User.name as the top-level fullName attribute,
    regardless of whether legal_address has a usable split name
    """
    user = UserFactory.create(name="Joe Middle Smith")
    user.legal_address.first_name = "Given"
    user.legal_address.last_name = "Family"
    user.legal_address.save()

    assert _adapter(user).to_dict()["fullName"] == "Joe Middle Smith"


def test_learn_user_adapter_to_dict_no_split_without_full_legal_address():
    """to_dict() does not guess a given/family split from User.name when
    legal_address has no name on file - a wrong guess is worse than blank
    """
    user = UserFactory.create(name="Joe Middle Smith")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {"givenName": "", "familyName": ""}


def test_learn_user_adapter_to_dict_single_token_name_not_split():
    """A single-token name isn't guessed into a given/family split either;
    it's still sent whole via fullName
    """
    user = UserFactory.create(name="Madonna")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    adapted = _adapter(user).to_dict()
    assert adapted["name"] == {"givenName": "", "familyName": ""}
    assert adapted["fullName"] == "Madonna"


def test_learn_user_adapter_to_dict_no_name_data():
    """No legal_address and no User.name results in a blank given/family name"""
    user = UserFactory.create(name="")
    user.legal_address.first_name = ""
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {"givenName": "", "familyName": ""}


def test_learn_user_adapter_to_dict_partial_legal_address_not_trusted():
    """A half-filled legal_address isn't trusted; returns blank rather than
    guessing a split from User.name
    """
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "OnlyGiven"
    user.legal_address.last_name = ""
    user.legal_address.save()

    assert _adapter(user).to_dict()["name"] == {"givenName": "", "familyName": ""}


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


def _sync_mocks(mocker):
    """Patch on_commit to run inline and return the two queued task mocks.

    on_commit is patched at users.adapters, matching courses/signals_test.py -
    pytest.mark.django_db wraps each test in a transaction that never commits,
    so registered callbacks would otherwise never run.
    """
    mocker.patch(
        "users.adapters.transaction.on_commit", side_effect=lambda callback: callback()
    )
    return (
        mocker.patch("openedx.tasks.update_edx_user_profile.delay"),
        mocker.patch("openedx.tasks.change_edx_user_email_async.delay"),
    )


def _unchanged_payload(user, **overrides):
    """A from_dict payload that reproduces the user's current state.

    from_dict() writes userName unconditionally, so it always has to be present
    or the save would blank the username out.
    """
    return {
        "active": user.is_active,
        "userName": user.username,
        "externalId": user.scim_external_id or "1",
        "fullName": user.name,
        **overrides,
    }


def test_edx_sync_attrs_cover_to_dict():
    """Every to_dict() key must be classified as either synced to Open edX or
    explicitly not synced. Diffing runs over _scim_attrs() - the same data
    to_dict() is built from - filtered to an allow-list, so an unclassified
    attribute would silently never reach edX; this test makes adding or renaming
    an attribute fail loudly instead of quietly changing what gets synced.
    """
    user = UserFactory.create()

    assert not (EDX_SYNC_ATTRS & EDX_UNSYNCED_ATTRS)
    assert set(_adapter(user).to_dict().keys()) == EDX_SYNC_ATTRS | EDX_UNSYNCED_ATTRS


def test_scim_name_change_queues_edx_profile_update(mocker):
    """A SCIM full name change pushes the profile to Open edX"""
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(name="Joe Smith")

    adapter = LearnUserAdapter(user)
    adapter.from_dict(_unchanged_payload(user, fullName="Joseph Smith"))
    adapter.save()

    user.refresh_from_db()
    assert user.name == "Joseph Smith"
    mock_profile.assert_called_once_with(user.id)
    mock_email.assert_not_called()


def test_scim_legal_address_name_change_queues_edx_profile_update(mocker):
    """A change to name.givenName/familyName queues the profile push too, even
    though those live on LegalAddress rather than on User - the diff runs over
    the SCIM representation, not over a hand-listed set of User columns
    """
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(name="Joe Smith")
    user.legal_address.first_name = "Joe"
    user.legal_address.last_name = "Smith"
    user.legal_address.save()

    adapter = LearnUserAdapter(user)
    adapter.from_dict(
        _unchanged_payload(user, name={"givenName": "Joseph", "familyName": "Smythe"})
    )
    adapter.save()

    mock_profile.assert_called_once_with(user.id)
    mock_email.assert_not_called()


def test_scim_email_change_queues_edx_email_update(mocker):
    """A SCIM email change pushes the email to Open edX"""
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(email="old@example.com")

    adapter = LearnUserAdapter(user)
    adapter.from_dict(
        _unchanged_payload(user, emails=[{"value": "new@example.com", "primary": True}])
    )
    adapter.save()

    user.refresh_from_db()
    assert user.email == "new@example.com"
    mock_email.assert_called_once_with(user.id)
    mock_profile.assert_not_called()


def test_scim_email_case_change_does_not_queue_edx_email_update(mocker):
    """A case-only email change is not a real change - update_edx_user_email
    costs a full Open edX OAuth handshake, so it must not fire for one
    """
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(email="joe@example.com")

    adapter = LearnUserAdapter(user)
    adapter.from_dict(
        _unchanged_payload(user, emails=[{"value": "JOE@example.com", "primary": True}])
    )
    adapter.save()

    mock_email.assert_not_called()
    mock_profile.assert_not_called()


def test_scim_no_op_save_queues_nothing(mocker):
    """A SCIM write that changes nothing queues no Open edX work"""
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(name="Joe Smith")

    adapter = LearnUserAdapter(user)
    adapter.from_dict(_unchanged_payload(user))
    adapter.save()

    mock_profile.assert_not_called()
    mock_email.assert_not_called()


def test_scim_unknown_attributes_queue_nothing(mocker):
    """Attributes we do not model must never trigger an Open edX push.

    The diff is taken over to_dict(), which is rendered from our own models and
    never echoes unrecognized request keys, and is then filtered to
    EDX_SYNC_ATTRS - so an undocumented attribute cannot queue edX work.
    """
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(name="Joe Smith")

    adapter = LearnUserAdapter(user)
    adapter.from_dict(
        _unchanged_payload(
            user,
            nickName="Joey",
            title="Dr",
            **{"urn:ietf:params:scim:schemas:extension:custom:2.0:User": {"dept": "x"}},
        )
    )
    adapter.save()

    mock_profile.assert_not_called()
    mock_email.assert_not_called()


def test_scim_active_change_queues_nothing(mocker):
    """The active flag is deliberately not synced: Open edX lists is_active in
    AccountUserSerializer.read_only_fields, and sending a read-only key makes
    edX 400 the entire PATCH - which would take the name sync down with it
    """
    mock_profile, mock_email = _sync_mocks(mocker)
    user = UserFactory.create(is_active=True)

    adapter = LearnUserAdapter(user)
    adapter.from_dict(_unchanged_payload(user, active=False))
    adapter.save()

    user.refresh_from_db()
    assert user.is_active is False
    mock_profile.assert_not_called()
    mock_email.assert_not_called()


def test_scim_create_queues_nothing(mocker):
    """A newly created SCIM user has no Open edX account to update yet"""
    mock_profile, mock_email = _sync_mocks(mocker)

    adapter = LearnUserAdapter(User())
    adapter.from_dict(
        {
            "active": True,
            "userName": "brandnew",
            "externalId": "kc-brandnew",
            "fullName": "Brand New",
            "emails": [{"value": "brandnew@example.com", "primary": True}],
        }
    )
    adapter.save()

    assert User.objects.filter(username="brandnew").exists()
    mock_profile.assert_not_called()
    mock_email.assert_not_called()


def test_scim_multi_operation_patch_queues_profile_update_once(mocker):
    """django_scim calls save() once per PATCH operation, so a request touching
    the name twice must still queue a single Open edX profile push
    """
    mock_profile, _ = _sync_mocks(mocker)
    user = UserFactory.create(name="Joe Smith")

    adapter = LearnUserAdapter(user)
    adapter.handle_operations(
        [
            {"op": "replace", "path": None, "value": {"fullName": "Joseph Smith"}},
            {"op": "replace", "path": None, "value": {"fullName": "Joe Smythe"}},
        ]
    )

    user.refresh_from_db()
    assert user.name == "Joe Smythe"
    mock_profile.assert_called_once_with(user.id)


def test_scim_save_survives_broker_failure(mocker, caplog):
    """A broker outage must not turn a SCIM write into a 500 - the user is still
    saved and the failure is only logged
    """
    mock_profile, _ = _sync_mocks(mocker)
    mock_profile.side_effect = Exception("broker down")
    user = UserFactory.create(name="Joe Smith")

    adapter = LearnUserAdapter(user)
    adapter.from_dict(_unchanged_payload(user, fullName="Joseph Smith"))
    adapter.save()

    user.refresh_from_db()
    assert user.name == "Joseph Smith"
    assert "Failed to queue edX profile update" in caplog.text
